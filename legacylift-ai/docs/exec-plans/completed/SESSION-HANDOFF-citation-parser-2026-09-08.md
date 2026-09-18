# Session handoff — SPENT 2026-09-09, kept only for the probe table

> ## ⚠️ THIS FILE IS SPENT. Both of its jobs are closed.
> Job 1 (the multi-range parser defect) shipped 2026-09-08. Job 2 (rounds 2–4) is no longer the
> open decision it describes: a code review, a Phase 3 rehearsal and a scoped two-round run have
> since happened, four more defects were found and fixed, and **the current state lives in
> [`reqs-to-data-store.md`](../active/reqs-to-data-store.md)'s `Progress` and `Surprises & Discoveries`**.
> Read that, not this. What is still worth having here is the *Already verified with a reproducible
> probe* table below — those probes cost real time and re-running them buys nothing. Everything
> else, including the code-review brief at the end, is history.
>
> The one substantive correction this file needs: its resume advice assumed the round-1 agent cache
> was reachable. Resume is same-session only and that session is gone, so `wf_5d70da43-474` is no
> longer resumable and a continuation is a full re-run.

# Original handoff — fix `parse_citation`'s multi-range defect; rounds 2–4 stay open

**Written 2026-09-08.** Branch `feature/reqs-to-data-store`, HEAD `ce2b1292`, working tree clean,
suite **1,250 passed, exit 0**.

Disposable. Durable facts are already in the plan and the deferred list — this file says what to do
next and what not to spend a pass on.

> **Update 2026-09-08 — job 1 is done.** `parse_citation` now emits one triple per comma-separated
> range; 1,256 tests pass, exit 0; re-parsing the saved round-1 JSON leaves **0 whole-file triples
> across 133 rules**, with the 9 measured rules expanding as predicted. Entry 11 shipped and was
> removed from the deferred list. `requirements stats` was deliberately **not** changed — see the
> plan's `Surprises` bullet for why the label question lapsed with the fix. **Job 2 below still
> stands: rounds 2–4 remain the user's call, and nothing has been ingested.**

## Your job

1. ~~**Fix `parse_citation` so a multi-range citation parses.**~~ **Done 2026-09-08** — see the
   update above. What it changed and why is recorded in
   [`reqs-to-data-store.md`](../active/reqs-to-data-store.md)'s `Progress` and `Surprises`, which are now
   the definitive record; entry 11 of the deferred list is gone.
2. **Do not decide rounds 2–4.** Whether to continue the extraction to four rounds is deliberately
   left to the user; see *The open question* below. Do not launch a continuation on your own
   initiative — it is hours of model time and the user has been capping it round by round.

## Why the parser fix is first, and what "before" means

The fix is cheap now and expensive later. An affected rule gains a second anchor, which changes its
**tier-1 `dedupe_key`** — so doing this before the first kept ingest is a code change, and doing it
after is a re-key migration over `knowledge.sqlite`. **Nothing has been ingested yet.** `gr` and
`gr_run` are empty (verified this session), so the window is open and closes the moment Phase 3
runs.

Two things entry 11 states that you should not re-derive: `parse_citation` is deliberately the
**single** parser shared by the coverage denominator and the ingest anchor resolution, so both move
together; and the docstring's existing reasoning about prose landing in `source` is correct and
unaffected — it simply never considered a well-formed citation naming two ranges.

One thing entry 11 leaves to you: whether `requirements stats` should distinguish the two faults
that now share the `unresolved` label. The plan's own `Surprises` entry flags this as newly
load-bearing on this corpus. It may be a second deferred entry rather than part of your change.

## Already verified with a reproducible probe — do not re-check

Each of these cost a probe this session. Re-running them buys nothing.

| Claim | How it was probed |
|---|---|
| The classifier limit is on **output schema size**, and only that | 7 synthetic schemas, 2K–14K bytes: 4,000 spawns, 6,000 blocked |
| It is **not** the agent type, **not** `type:['string','null']` with `null` in an `enum`, **not** `oneOf` on a nested object | three isolating probes, all three pass |
| It is **not** the prompt | real mining prompt + small schema spawned and returned a good rule |
| The fixed `RULES_SCHEMA` (2,239 b) works end to end | the `maxRounds:1` run: 238 agents, 0 errors, 133 rules |
| `A1` holds on live output | the gate, on 133/133 rules — see the plan's *Concrete Steps* |
| Multi-range citations mis-parse in **both** strict and non-strict mode | direct call on 4 real citations, incl. a single-range control that parsed correctly — **fixed 2026-09-08**, re-verified over all 133 rules |
| CODE-relative is the citation base that `coverage` actually credits | same two files, two bases: 115 chunks vs 31 |
| Bedrock auth, dim 1024, unit-norm | one live `embed_documents` + `embed_query` through the unit's manifest |
| `A2` (no `legacylift-docs/` under the checkout) | filesystem `rglob` after a real `index --reset`, **not** `git status` |
| Every `symbols` row has `entity_class`/`anchor_key`/`content_hash` | SQL over the rebuilt index; `user_version` 0 → 2 |
| The eleven GR tables + `gr_fts` appear free on first open | observed on the real store, `user_version` still 1 |

## Not verified — where your value is highest

- **Nothing has been ingested.** `requirements ingest` has never run against real extractor output.
  MEAS-1, MEAS-2, MEAS-3, the Phase 4 merge acceptance test and `A3` are all untouched.
- **Rounds 2–4 have never run**, so the already-catalogued targeting block, the dry-round
  termination path and `stopReason: 'dry'` are unexercised. Only `round_cap` has ever been produced.
- **The citation base is luck, not a guarantee.** The mining agents emitted CODE-relative paths
  unprompted; nothing in `extract-rules.js` tells them to. Milestone 2 adds four more producers
  against the same schema.
- **`modality` came back `requirement` on all 133 rules.** No `expectation` has ever been produced,
  so that half of the enum is untested against live output.
- **`D-CONST` is the one SPEC-1 pattern the corpus has never exercised.**

## The open question — rounds 2–4 (leave it open)

If and when the user says go: **continue with
`Workflow({scriptPath: <the ASCII copy>, resumeFromRunId: 'wf_5d70da43-474', args: {...}})`**, not a
fresh launch. Round 1's 238 agents replay from cache; rounds 2+ differ because the
already-catalogued block grows, so only round 1 is cached. A restart re-spends 67 minutes to
recompute identical results.

Two caveats. Resume is **same-session only**, so from a new session the cache is gone and this
becomes a full re-run — worth telling the user before they decide. And if you have changed
`parse_citation` by then, the round-1 JSON on disk is still the input Phase 3 replays; the parser
change affects how it is *read*, not what it says, so no re-extraction is implied.

The corpus that already exists is enough for some of Step 10: 40 of 133 rules carry a
`structuredBody` (24 `decision_table`), so MEAS-2 and MEAS-3 have real data from round 1 alone.
MEAS-1 wants the largest corpus available, since it measures intra-run collapse.

## The one irreplaceable artifact

`repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app/knowledge/extracted-rules-round1.json`
— 513 KB, 133 rules, 67 minutes of model time, **one copy, in no commit and uncommittable**
(`.gitignore:92` covers the whole tree). Do not overwrite it; the `-round1` suffix exists so a later
full run cannot. Step 9's JSONL export is the intended durable backup and only becomes available
after an ingest.

The rebuilt index, the re-tagged `knowledge.sqlite` and the re-verified `PREFLIGHT.md` are in the
same un-backed-up tree.

## Environment

Read [`reqs-to-data-store.md`](../active/reqs-to-data-store.md)'s *Concrete Steps* → **Step 10 Phase 2, as
actually run** before launching any workflow. It carries the four transforms a launch needs and the
three that each cost a launch this session; the memory note `workflow-launch-harness-quirks` carries
the same list.

Two things that were only in a session scratchpad, so that they are not lost with it:

- **The A1 gate** classifies every citation as CODE-relative / session-cwd-relative / absolute /
  unresolvable and fails if any need normalizing. Two mechanics cost a re-run: the rules are under
  **`confirmedRules`**, not `rules`, and a trailing range may be a **comma-separated list**, so a
  `:\d+-\d+$` strip is not enough — which is how the defect you are about to fix was found rather
  than assumed. Rebuild it rather than hunting for the file.
- **Schema size is measurable without a launch**: cut `extract-rules.js` at
  `const seen = new Map()`, strip `export` from `meta`, prepend an `args` object, and
  `console.log(JSON.stringify(RULES_SCHEMA).length)` under node. Keep it under ~4 KB.

`legacylift-search` on `PATH` is broken — use `tools/legacylift_search/.venv/Scripts/`. Bedrock
credentials are in `.claude/settings.local.json` under `env` (`AWS_BEARER_TOKEN_BEDROCK`,
`AWS_REGION`); export them for anything that embeds. Run the suite as a bare `-m pytest` —
`pyproject` already sets `addopts = "-q"`, so a second `-q` suppresses the summary line.

## For the code-review pass (2026-09-08)

**Two commits, reviewed together or in order.** `ce2b1292` deleted four schema constants and moved
11 KB of prose between two delivery channels, and the only thing that has exercised it is one live
run plus a suite that never spawns an agent. The parser commit on top of it changes a function whose
output is a **hash input**.

What the parser change actually did, so a reviewer does not have to reconstruct it:

- `_parse_range_list` is new, and is the old `split("-", 1)` body run once per comma-separated
  piece. `parse_citation` builds a `ranges` list where it used to build one `(start, end)`, and the
  trailing-range character test widened by exactly one character (`,`).
- The **return contract did not change** — the function already returned a list — so `resolve_anchor`,
  `gr_ingest.py` and the coverage denominator needed no edit. That is deliberate: it stays the
  single parser, so both consumers move together.
- A malformed piece fails the **whole entry** rather than half-keeping it. Half a citation keys a
  rule on a subset of its evidence and looks healthy.

Where a reviewer's value is highest, because these were reasoned about rather than tested to
exhaustion: whether widening the character test can capture a *path* that legitimately ends in
digits and commas after its last colon; whether one triple per range is right versus one triple
spanning min-to-max (it is not — the ranges need not be contiguous, and the span form would hash
lines the citation never named); and whether `gr_citation`'s `(gr_id, path, start, end)`
uniqueness plus `gr_ingest`'s existing `seen_tuples` collapse really covers a rule citing the same
range twice across two entries.

Already measured, so do not re-probe: 1,256 tests pass, exit 0 (was 1,250); re-parsing the saved
round-1 JSON leaves **0 whole-file triples across 133 rules**, with exactly the 9 measured rules
expanding.

- **`simplify`** — a pass on the `parse_citation` change is still worth it; the function's docstring
  is load-bearing and grew.
- **`/loop`** — only if the user approves rounds 2–4 and wants the long run babysat. Do not use it
  to poll a workflow you launched; the harness notifies on completion.

Do **not** reach for `fact-graph` or the documentation skills here. This work is the Python package
and one workflow file; the documentation skills are the other half of the product.
