# SESSION HANDOFF — Phase 6, the second live extraction — 2026-09-10

> ## ✅ DISCHARGED 2026-09-10 — Phase 6 and Phase 7 both ran; Step 10 is complete.
>
> Discharged by commit `8e69ee45`, which moved this file. `wf_fe5c5435-2db` ran the second four-round
> extraction (595 agents, 0 errors, 16.76M subagent tokens, 3 h 6 m); the corpus is saved as
> `extracted-rules-4round-run2.json` and was ingested into a scratchpad **copy** of the store, per
> the settled decision this file states. **`rules_candidate` = 211 of 435 offers (48.5%)** —
> the deliverable. `rules_new` = 66, `rules_merged` = 158.
>
> **The prediction in *Phase 6 is more interesting than the runbook makes it sound* was right:**
> `semantic` merge candidates appeared for the first time — 39 raised, 14 surviving with
> `similarity` 0.7422–0.9391, all fourteen cross-run pairs. The harness's "roughly 18" was
> conservative by about a factor of two.
>
> **Two of this file's own claims were corrected by measurement, and the corrections are the
> valuable part.** Item 4 predicted the export churn would be cosmetic `updated_at` movement; it is
> in fact a wholesale replacement of every extractor-owned field on 91 rows (correct behaviour —
> `gr_fields`' partition protected all nine human-writable columns — but not cosmetic). And the
> ingest banner's per-reason candidate tally turns out not to be reproducible from the store, which
> nothing predicted; it is now `pending/deferred-small-items.md` entry 17.
>
> **All durable state is in the plan**, per this file's own instruction: `Progress`,
> `Outcomes & Retrospective` → *Step 10 Phase 6*, `Concrete Steps` → *Step 10 Phase 6, as actually
> run*, and `Surprises & Discoveries` → *What the second four-round run discovered*. The runbook's
> status banner is updated. **Next action moved to Milestone 1.5**, whose frozen data point
> survived intact because the real store was never written to.
>
> The two open items this file said were not Phase 6's job were left filed, as instructed: the
> untracked `requirements.jsonl` and `pending/dedupe-key-tier-mismatch.md`.

**Disposable.** Durable facts are in [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) and
[`active/reqs-to-data-store-step10-runbook.md`](../active/reqs-to-data-store-step10-runbook.md). This file
says only what to do next and what not to waste a pass on. If you find yourself about to write a
measurement or a decision here, put it in the plan instead.

Branch `feature/reqs-to-data-store`, tree clean, nothing pushed. This file is the branch tip;
`git log --oneline -8` shows the Phase 3-5 series that produced everything it cites.

---

## The job

**Phase 6 (runbook §9), then Phase 7 (§10).** Run `/modernize-extract-rules` against the NNG app
unit a *second* time and record `rules_new` / `rules_merged` / `rules_candidate`. `rules_candidate`
is the deliverable — **Step 6's key-instability measurement**, i.e. how much the extractor's
`ruleClass` and `pattern` moved between two runs over identical code.

Read in this order — do not start from this handoff alone:

1. `reqs-to-data-store.md` → `Progress`. The definitive state.
2. The same plan's **Milestone 1.5 → *The new-run data point, frozen 2026-09-10 before Phase 6***,
   and its `Decision Log` entry on ingesting Phase 6 into a copy. Both are why the next section is
   an instruction rather than a question.
3. `reqs-to-data-store-step10-runbook.md` — its **status banner** first, then **§9** and **§10**.
4. `Concrete Steps` → *Step 10 Phase 2, as actually run — the four-round run* for the launch
   mechanics, which are fiddly and already solved.

**Phase 6 is deliberately a softer criterion than Phase 4.** The extractor is a language model and
its output is not reproducible, so a non-zero `rules_new` is **not** a merge defect. Treat it as one
only if the same rules also fail to appear in `requirements list --candidates`.

---

## ⚠ SETTLED — ingest Phase 6 into a COPY of the store, not the real one

**The user decided this on 2026-09-10; it is not an open question and does not need re-raising.**
The reasoning is the plan's `Decision Log`; the recipe is the runbook's **§9**, which now carries it.
In short: `rules_candidate` needs only a store that already holds run 1, and a copy has that, so
there is no reason to spend the real store's single-run state on it.

What the real store's single-run state is worth protecting: **379 requirements over 118 distinct
files cited**, the pair Milestone 1.5 compares against BASE-ENH's 470/148. `gr.first_seen_run_id`
would keep the *rule* count recoverable after a real merge, but **distinct-files-cited would not** —
`gr_citation` has no `run_id`, and a merged run's citations attach to existing requirements
indistinguishably. Ingesting for real would therefore settle Milestone 1.5's framing as a *side
effect* of running Phase 6, which is the thing to avoid. **Nothing is foreclosed**: the merged store
can be produced later from the same saved corpus once the comparison is chosen with numbers in hand.

**The one way to get this wrong: copy `knowledge/chroma/` as well as `knowledge.sqlite`.** That is
the single difference from the Phase 5 copy recipe, and it is load-bearing — see the next section.
Do **not** empty the `gr` tables the way the `A3` copy did; Phase 6 needs run 1 present.

---

## Phase 6 is more interesting than the runbook makes it sound — one prediction worth testing

**It is the first ingest that can actually exercise stage two's semantic half.** Phase 5 established
that the semantic half has never run against a populated collection: the vector half runs *after* the
commit (`gr_ingest.py:1049`), so a first ingest queries an empty collection, and on a re-ingest every
rule matches stage one so stage two is never reached. Phase 6 is neither of those — the collection
now holds 379 vectors, and Phase 6's genuinely new rules will reach stage two.

So **watch `merge candidates raised` for a `semantic` reason.** Every one of the 148 candidates in
the store today is `drift` (85) or `range_overlap` (63); `similarity` is NULL on all of them.
A `semantic` row with a non-NULL `similarity` would be the first ever produced. Phase 5's harness
predicts roughly **18 novel pairs** at the default `SEMANTIC_DISTANCE_MAX = 0.35` over the current
corpus, so the expectation is "some, but not many". **Zero would be worth investigating** rather
than shrugging at.

---

## Already verified with a reproducible probe — do not re-check

Everything below was measured in the 2026-09-10 session. Numbers and interpretation live in the
plan's `Outcomes & Retrospective` (*Step 10 Phase 3, as measured*, *Step 10 Phase 4*, *Step 10 Phase
5*); this list exists so you do not spend a pass reproducing them.

| claim | probe |
|---|---|
| `MEAS-1` = 106 offers / 48 rows, **verdict true-same** | census of all 48 groups joined to `confirmedRules[offer_ordinal]` |
| `MEAS-2` = 39, `MEAS-3` = 3–8 rules, median 5, 84.6% ≤ six | SQL over `structured_body` |
| **Merge acceptance test PASSES on the real store** | two re-ingests + field-by-field diff of six tables across a third |
| Ingest is idempotent in content; only `updated_at` and two surrogate ids churn, on exactly `MEAS-1`'s 48 rows | full row snapshots either side of ingest #3, sets compared |
| **`A3` PASSES** — degraded ingest exits 0 and names `reindex-vectors`; it then fills 379/379 | credential removed for one command against a scratch store copy |
| `MEAS-1` is exactly reproducible from the corpus file | the `A3` ingest reproduced Phase 3 figure for figure |
| Semantic half has never run; both defaults are fine as they are | read-only neighbour harness over the populated collection |
| Two exports of an **unchanged** store are byte-identical | back-to-back export, `cmp` |
| The one prose citation degrades to 4 `unresolved` anchors, does not abort | the rule is in the store, alone with zero resolved citations |
| `export` refuses an incomplete corpus (exit 1) and needs `--allow-incomplete` | both invocations |

**Two recipes worth keeping, both pure functions of a saved corpus.** *Collapse census*: join
`gr_run_hit.offer_ordinal` back to `confirmedRules[ordinal]` and print the surviving row's name
beside every offered name — this is the entire basis of the true-same verdict and it works only
because the corpus file still exists. *Split census*: group `gr` by `dedupe_key_anchor_only`, then
check every internal pair against `gr_merge_candidate`.

---

## Not verified — this is where your value is highest

1. **`rules_candidate` itself.** The whole deliverable. Unspent, and it needs a live run.
2. **Whether a `semantic` merge candidate ever appears.** See the prediction above.
3. **Whether Phase 6 widens the cited-file set.** Milestone 1.5 requires rule count and
   distinct-files-cited to be reported together, so this is the axis that matters, not the rule count.
4. **Whether entry 16's `updated_at` churn shows up in a Phase 6 export diff.** Predicted yes, on the
   48 rows plus whatever Phase 6 collapses. It is cosmetic; do not let it look like data loss.
5. **What `maxRounds` to use.** Four rounds did **not** saturate last time — new rules per round were
   112 / 115 / 92 / 118, with round 4 the largest — so there is no decay curve to lean on and the
   round count is a budget decision. The plan's `Progress` says this; do not re-derive it.

---

## Traps that have each cost a cycle

- **`legacylift-search` on `PATH` is broken.** Use `tools/legacylift_search/.venv/Scripts/`.
  `py -3.12` is not installed either.
- **Workflow launch quirks, all solved in `Concrete Steps` → *the four-round run*.** Non-ASCII fails
  the approval dialog's control-char guard; `args` arrives as a JSON **string**, not an object; a
  backtick in replacement prose breaks the template literal it lands in; and **assert the transforms
  against the text you are inserting, not only the text you are removing** — two of four transforms
  bit inside the transform script itself last time.
- **Disable sleep before launching.** The laptop slept mid-run and the resume delivered
  `[Request interrupted by user]` to the agent then in flight rather than resuming it.
- **`journal.jsonl` in the run's transcript directory is a real recovery path** — one
  `{"type":"result"}` line per completed agent with its full return value. A run that never returns
  is not a lost corpus.
- **`resumeFromRunId` is dead for the prior runs.** Prompt fixes landed after all of them, so no
  mining agent replays from cache.
- **Never overwrite an extraction corpus.** Five exist now plus a journal backup; all are untracked
  and unreproducible. **Save Phase 6's return value verbatim to a NEW name before any gate.**
- **`--repo-root` is load-bearing on `ingest`**, read three times — store location, cited line
  ranges for span hashes, and `index.sqlite` for anchor resolution.
- **Do not run `/modernize-assess`.** It re-authors `domains.json`, moves every `derived` subject and
  silently deletes the hand-added `vendored_globs` / `own_identities`. Settled — runbook §2.
- **The `derived`-subjects gate runs before any measurement.** If every subject is `llm_named`,
  `tag-domains` did not take.
- Bedrock credentials are in `.claude/settings.local.json` under `env` (`AWS_BEARER_TOKEN_BEDROCK`,
  `AWS_REGION`) — do not echo values into a transcript.

---

## Suggested skills

- **`code-modernization:modernize-extract-rules` — this time it IS the right tool.** The previous
  handoff said not to invoke it because Phase 2 was complete; Phase 6 is a deliberate second
  extraction, so it is exactly what runs. Launch it the way the four-round run was launched.
- **`code-modernization:repair-structured-bodies` — only if Phase 6's bodies fail validation.** All
  88 of the current corpus's bodies validate, so it was not needed last time. Check Phase 6's own
  output before deciding; that check is a pure function of the saved JSON.
- **`/code-review`** — only if Phase 6 produces code changes. The plan document itself is closed to
  further review rounds; its `Surprises & Discoveries` gives the measured reason.
- Use the runbook's §11 per-phase model split rather than improvising one. **The launch and the
  saving of the return value belong in the main session** — hours of model time are at stake.

---

## When this is done

Phase 7 (§10) is the recording step, and it is the last of Step 10. Then the **Next action moves to
Milestone 1.5**, whose frozen data point is already in place. Record everything in the plan's
`Progress`, `Outcomes & Retrospective` and `Concrete Steps` — **state stays in the plan; the runbook
records nothing** — and update the runbook's status banner. Then move this file to
`docs/exec-plans/completed/` with a `DISCHARGED` banner naming the commit, per `docs/exec-plan.md`.

**Two open items are not Phase 6's job and should not be folded into it.** The exported
`requirements.jsonl` is still untracked, because `.gitignore:108` ignores the whole
`repos/nng-app-legacylift-analysis/` tree — committing client-derived requirements is the
maintainer's call and no `git add -f` has been run. And `pending/dedupe-key-tier-mismatch.md`,
`pending/deferred-small-items.md` entries 15 and 16 are all measured and filed; leave them filed.
