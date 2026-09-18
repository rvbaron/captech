# ExecPlan status

**This file is the current status of LegacyLift's in-flight engineering work.** It is the routing
layer: which plans are active, what each one covers, and what a reader must know before opening it.

## How to use this file

- **Status lives here, not in `CLAUDE.md`.** `CLAUDE.md` describes what an ExecPlan *is* and links
  here; it must not carry milestone progress, measurements, next actions or test counts. When a plan
  advances, update this file — never that one.
- **Each plan is still the definitive record of its own state.** Milestone progress, measurements,
  acceptance numbers and the next action live inside the plan document. What belongs here is only
  what a reader needs in order to *choose* a plan and open it without a trap: where its state is
  recorded, which companion file to start from, and what must not be re-derived or overwritten.
- **Read the plan before touching the code it covers.**

The ExecPlan format itself is defined in [`exec-plan.md`](./exec-plan.md).

---

## Active plans

| Plan | What it covers |
|---|---|
| [`active/reqs-to-data-store.md`](./exec-plans/active/reqs-to-data-store.md) | Moves generated requirements out of markdown into `knowledge.sqlite`, and rewrites `/modernize-extract-rules` to author them. **This plan is the definitive record of its own state** — milestone progress, test counts, next action and the `CR-` code-review series all live in it, not here; read its preamble and `Progress` before starting, and record what you do there. It is also settled design: reviewing is finished, so do not open another review round against the plan document — its `Surprises & Discoveries` gives the measured reason. Per-finding record of the pre-implementation reviews (the `PR-` series) is in the companion archive `active/reqs-to-data-store-additional-info.md`; consult it before proposing a change the reviews may already have rejected. **Milestone 1 is COMPLETE as of 2026-09-10 — Step 10 ran all seven phases and the next action is Milestone 1.5**, the SPEC-2 baseline comparison; **start it from `active/SESSION-HANDOFF-milestone1.5-2026-09-10.md`**, which carries the reading order, the pre-flight measurements already taken, the one gate to decide before ingesting run 2 into the real store, and nine traps. `active/reqs-to-data-store-step10-runbook.md` is now DISCHARGED and must not be re-run; its banner says so. Two things a reader should not re-derive: the two NNG extraction corpora (437 and 435 rules) are **unreproducible, untracked and must never be overwritten** — six now sit in `analysis/customer.ple.nng.app/knowledge/` — and the real store deliberately holds **run 1 only**, because Phase 6 was ingested into a scratchpad copy to protect Milestone 1.5's frozen 379/117 pair. |
| [`active/semantic-code-search-graph-index.md`](./exec-plans/active/semantic-code-search-graph-index.md) | The Layer-0 index — discovery, extraction, chunking, embeddings, the code graph, and lexical/vector search. **Its `Progress` list is the definitive record of which milestones are done**; do not restate that here. One cross-plan coupling worth knowing before you read either document: the requirements plan's data-flow block (`reads[]`/`writes[]`) is gated on this plan's Milestone 26, `uses_table` lineage correctness. |
| [`active/code-graph-construction.md`](./exec-plans/active/code-graph-construction.md) | Reference for how Layer 0 builds symbols, edges, facts and domain tags today. |
| [`active/layer0-extraction-gap-detection.md`](./exec-plans/active/layer0-extraction-gap-detection.md) | A `legacylift-search gaps` command reporting what Layer 0 never opened. Design settled (27 decisions); **M0 and M1 shipped 2026-09-02**, and the **Layer-0 coverage widening shipped 2026-09-08** out of milestone order — eight `include_globs`, seven language registrations, and a shared `provenance.py` that makes `discover_source_files` apply the walk's third-party rules. NNG's gap 19.60% → **0.00%** of first-party bytes; discovery 1,229 → **1,504** files. **M2 — the `gaps` command — is next.** **The plan carries its own milestone state, acceptance numbers and next action** — read its `Progress`, its `M1 as built` section and the `Surprises & Discoveries` entry *The 2026-09-08 coverage widening*; do not restate them here. Two things a reader must not re-derive: **M3's acceptance moved and is re-pinned, M0–M2/M4's did not** (the acceptance manifest now pins the historical 27 globs on purpose), and `/modernize-assess` authors neither `vendored_globs` nor `own_identities`, so re-running it on NNG silently deletes them. Before proposing a design change, check `pending/layer0-extraction-gap-detection-decision.md`, the audit trail of what was already rejected. |

## Design records

Worth knowing about before proposing changes to `fact-graph` or the Layer-0/Layer-1
split: `pending/fact-graph-decision.md` (§5a.5 is measured, and wins over the earlier sections;
§5a.6 lists three unowned Layer-0 pieces) and `pending/fact-graph-explanation.md` (§9 is the
measured output, and corrects §§2–8).

## Pending deliverables

Eight are declared so that none reads as an omission. **Each file is the
definitive record of its own state** — measurements, open questions and next action live there, not
here.

- `pending/reqs-review-ui.md` — Milestone 4 of the requirements plan. **Partly shipped: a
  read-only Milestone 1 is BUILT and lives at [`platform-ui/`](../platform-ui/)**, the .NET 10 +
  Angular 21 review surface that is v4's third deployable component — so this is the one pending
  file with code already merged against it. Two routing facts before you open it. First,
  [`platform-ui/README.md`](../platform-ui/README.md) is the definitive record of what M1 built,
  how to run it and what the data forced; the plan file carries the fifteen *Decisions of record*
  behind it and the undesigned remainder. Second, **it is deliberately not a conforming ExecPlan**
  — no Plan of Work, no acceptance criteria — which was a decision taken against a demo deadline,
  not an omission to correct. Everything past read-only (editing, state transitions, merge
  resolution, bulk operations) is still undesigned and blocked on the reviewer-identity question
  that `set_state` forces.
- `pending/durable-loc-counts.md` — LOC is computed at least three times per engagement and stored
  zero times. Proposes a `line_count` column on `repo_files`, free to populate because discovery
  already reads each file whole for its SHA-256. Needs the versioned-migration machinery from the
  requirements plan's M0.
- `pending/embed-everything-evaluation.md` — **~70% of chunks never receive a dense vector**, on both
  reference corpora. Calls for a recall/precision evaluation, not a flag flip.
- `pending/dto-catalog-bounding.md` — two defects in `/modernize-extract-rules`' Data objects phase,
  found by the 2026-09-10 four-round run. The loud one: an unbounded response stalled the agent at
  ~100 KB. The damaging one: `ruleNames.slice(0, 250)` meant **187 of 437 rules were never shown to
  the DTO agent**, so `consumedBy` is silently 56.5% complete while looking finished. **`DTO_SCHEMA`
  is 543 bytes — this is NOT the `RULES_SCHEMA` size defect**, and shrinking the schema is the wrong
  fix. Off Milestone 1's path: `dataObjects` is never ingested. **Partly mitigated 2026-09-14 and
  the distinction matters: the truncation is now DISCLOSED, not fixed.** The pre-v4.0.0 review ruled
  that a v4 deliverable must not present 56.5% completeness as finished, so `extract-rules.js`
  returns `dataObjectsCoverage` and `/modernize-extract-rules` renders an admonition from it. The cap
  and the unbounded response are unchanged, so both defects are open exactly as the file states them
  — but a batching design must now keep `dataObjectsCoverage` meaningful rather than remove it.
- `pending/search-graph-expansion.md` — filed 2026-09-14 from the pre-v4.0.0 review, where it
  started as a documentation defect: `architecture.md` claimed hybrid search was "optionally
  expanded one hop along the graph", and `search.graph_neighbor_depth` has existed since
  `SearchConfig` itself, but **nothing on the search path has ever read it**. The claim is now
  corrected and the capability is this draft. **M1 is a measurement, not an implementation, and it
  gates everything**: graph expansion's failure mode is invisible precision dilution via high-fan-in
  symbols, so the plausible outcome is "do not build it, delete the knob". Two things a reader
  should not re-derive: the knob was kept rather than deleted as dead config *because* this draft
  exists (unlike the `languages` block removed the same day, which had no intended reader), and
  **the exposure is wider than one corpus** — `SearchConfig.graph_neighbor_depth` itself defaults to
  `1` in `config.py`, so a reader added without first changing that default switches expansion on
  **everywhere**, not only on the tracked CTCM manifest that also sets it explicitly. The default is
  now commented at its definition, and `tests/test_config.py:72` pins it.
- `pending/platform-ui-tests.md` — filed 2026-09-14 from the pre-v4.0.0 review. `platform-ui` ships
  as one of v4's three deployable components with **zero tests** — 948 lines of C# and 23 TypeScript
  files whose entire CI gate is `dotnet build` and `ng build` — while the other two components carry
  a 1,264-test suite. It is a **draft, not a conforming ExecPlan**, and it is scoped deliberately
  narrowly: not a coverage target, not browser automation. Two facts a reader should not re-derive:
  **the web test scaffold is already complete and idle** (`"test": "ng test"`, vitest 4 + jsdom
  installed, `tsconfig.spec.json` wired to `src/**/*.spec.ts` — only the spec files are missing), so
  the first web test is nearly free, whereas the API has no test project at all; and a `test` job
  that passes on an empty suite would be the same defect wearing a green badge, so
  `--passWithNoTests` must not be set. Read [`platform-ui/README.md`](../platform-ui/README.md) and
  `pending/reqs-review-ui.md` — its parent — before opening it.
- `pending/platform-ui-data-nrg-rebrand.md` — filed 2026-09-15. The reproducible recipe for
  de-identifying `platform-ui/data/`, the engagement-analysis copy the review UI renders, from NNG
  to a generic NRG. **It documents work already applied to the working copy, and it exists because
  `platform-ui/data/` is gitignored** — so that work is in no commit and is destroyed the moment
  `platform-ui/tools/prepare_data.py` regenerates the folder, which restores every NNG name. The
  plan carries the full survey, the substitution rules and the idempotent script; do not restate
  them here. Three traps a reader should not re-derive: **a SQL-query residue check is not
  sufficient** — rewritten rows leave the old text in freed SQLite pages, so the acceptance check
  greps the `.sqlite` files as binary and the script must `VACUUM`; **`ETS*` is schema vocabulary,
  not branding**, and only the full `ETSPii` system name was renamed (a bare `ETS` pass corrupts
  `SECRETS`, `sets`, `targets` and `assets`); and two `NORTHERN` sample values are preserved on
  purpose because one scenario asserts its own string length. The upstream corpora under
  `repos/nng-app-legacylift-analysis/` are deliberately untouched and still name the client.
- `pending/ctcm-submodule.md` — filed 2026-09-15 after Dependabot alerts on this repository were
  traced to the committed CTCM corpus: **135 of 139 open alerts came from manifests under
  `repos/ctcm`**, and the plan proposes mounting that path as a git submodule of
  `captechconsulting/ctcm` instead. It is a **draft, not a conforming ExecPlan**, and it is
  **blocked on two human decisions** it states in its `Decision Log` (which upstream commit to
  pin, and whether a private submodule is acceptable for everyone who clones this repo). Three
  facts a reader should not re-derive: **`.github/dependabot.yml` cannot suppress these alerts at
  all** — it configures version updates, while alerts come from the dependency graph, which has no
  path exclusion — whereas **CodeQL's `paths-ignore: repos/**` is working** and was never the
  problem; **removing the manifests from `HEAD` is sufficient, no history rewrite**; and **59
  LegacyLift-authored files live inside `repos/ctcm`** (the 57 fact-graph packs, their
  `index.json`, and a manifest) which a naive conversion deletes, which is why the plan's first
  milestone moves them out. The 135 alerts were dismissed as `not_used` on 2026-09-15 — a stopgap,
  not a fix.
- `pending/hosted-data-store.md` — AWS-hosted options for the two stateful halves of Layer 0, the
  vector store (today Chroma) and the graph store (today SQLite). It is **an analysis draft, not
  yet an ExecPlan**, and it is the only pending file gated on something outside engineering: the
  local-only constraint being relaxed for a specific engagement. It also holds the captured
  chunking/embedding performance discussion from the search plan's M17/M17b — including the
  correction that the "~7 s/chunk" figure was a CPU-contention artifact — so read it before
  re-deriving embedding throughput. Local Chroma + SQLite stays the default and the fallback.
- `pending/dedupe-key-tier-mismatch.md` — filed 2026-09-10 from the Step 10 Phase 3 ingest. The
  dedupe key's discriminator is tiered and chosen from **one row's own contents**, so a rule mined
  once with a `structuredBody` and once without is discriminated at different tiers and **its two
  rows can never match the exact key**. 34 anchor-only clusters / 54 excess rows on the NNG corpus,
  18 of them mixed. **Not a correctness defect** — all 34 clusters are fully queued as `drift`
  merge candidates, which is the behaviour `gr_ingest.py` argues for — and **no longer a free
  change**, because the store is now populated and altering the key is a re-key migration.

## Small items, and one standing draft

`pending/deferred-small-items.md` is a standing append-only list of measured changes too
small to own an ExecPlan — check it before filing a new draft for a one-file fix, and add to it
rather than burying a discovery in an unrelated plan's *Surprises* section. It now holds **fifteen**
entries, numbered 1–10, 12, 13, 15, 16 and 17, and the file itself is the definitive record of each. Two routing facts
worth knowing before picking one up: **four of the fifteen want the same thing — the first `knowledge.sqlite`
*column* migration** (whoever does one should do all four and pay for one migration instead of four),
and **entry 13 and `pending/dto-catalog-bounding.md` both touch
`.claude/skills/code-modernization/workflows/extract-rules.js`**, so whoever opens that file should
look at both.
**Entry 11 shipped on 2026-09-08** — `parse_citation` now accepts multi-range citations — and was
removed by the change that shipped it, which is the list's convention. **Entry 14 was promoted on
2026-09-10** to its own draft (below). Numbers are never reused, so **entry 17** (added 2026-09-10
from Step 10 Phase 6 — the ingest banner's per-reason merge-candidate tally cannot be reproduced
from the store, and the mechanism discards the semantic half's similarity scores) is the newest and
the next one written is 18; entries 15 and 16 were added the same day from Phases 4 and 5. **Entry
17 needs no `knowledge.sqlite` migration**, so it is not blocked behind the four that do.

`pending/indexer-credential-gate.md` was added 2026-09-08: the coverage widening put
`**/*.properties` into the allow-list, and 15 of NNG's carry cleartext credentials —
`application-prod1.properties` among them. Indexing them was a deliberate maintainer decision on
laptop-locality grounds; the draft records the measurement, the caveat that Bedrock embedding sends
them off the machine anyway, and the five open design questions.
