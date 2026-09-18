# SESSION HANDOFF — Milestone 1.5, the SPEC-2 baseline comparison — 2026-09-10

**Disposable.** Durable facts live in [`active/reqs-to-data-store.md`](./reqs-to-data-store.md) and
the SPEC-2 normative text in
[`pending/reqs-to-data-store-plan-draft.md`](../pending/reqs-to-data-store-plan-draft.md) from line
**5920**. This file says only what to do next and what not to waste a pass on. **If you are about to
write a measurement or a decision here, put it in the plan instead.**

Branch `feature/reqs-to-data-store`, tree clean, nothing pushed. **Milestone 1 is COMPLETE** as of
2026-09-10 — every step (1–5, 6a, 6, 7, 8, 9, 10) and all seven phases of Step 10.
`git log --oneline -5` shows the Phase 6 series that closed it.

---

## The job

**Milestone 1.5 produces one number and a written statement of what it may not be used to claim.**
Nothing in the store changes. The milestone is a *measurement and a write-up*, not a code change to
the pipeline — the only code it needs is two throwaway baseline parsers and a join.

Read in this order — do not start from this handoff alone:

1. `reqs-to-data-store.md` → **`Progress`** (the definitive state) and **`## Milestone 1.5`**
   (line ~3859). The milestone section is settled design; implement it literally.
2. The same plan's **Milestone 1.5 → *The new-run data point, frozen 2026-09-10 before Phase 6***.
   **This is the NEW side of the comparison and it is already measured.** Do not re-derive it.
3. **`NORMATIVE SPEC-2`** in the design draft, line 5920 — §S2.1 through §S2.6. §**S2.4 is
   mandatory and constrains what any deliverable may say.** Read it before reporting any number.
4. `Outcomes & Retrospective` → ***Milestone 1.5 pre-flight, measured 2026-09-10*** — the parser's
   ground truth, all verified, plus two hazards that will otherwise cost you a cycle.

**The order of work is fixed by the plan and is not a preference:** parse both baselines → **run the
BASE-ORIG-vs-BASE-ENH noise floor FIRST** → only then compare NEW against each. Doing the noise
floor after seeing the new numbers is, in the plan's words, "how the exercise turns into a post-hoc
story."

---

## What you already have, and must not re-measure

**The NEW side is done.** The real store holds run 1 alone, deliberately:

| | value |
|---|---|
| requirements | **379** |
| **distinct files cited** | **117 real files** (118 distinct `relative_path` values, one of which is a 445-char prose string) |
| citations | 383 — 375 symbol, 4 file, 4 unresolved |
| by category | Validation 168, Calculation 74, Policy 69, Lifecycle 68 |
| by rule class | behavioral 196, definitional 183 |
| provenance | one run, four rounds, `stop_reason=round_cap` — **a floor, not a sweep** |

**Report 379 / 117 against BASE-ENH's 470 / 148 — single run against single run.** Comparing 379
against 815 is explicitly forbidden (815 is a merge of three scoped runs).

**Both figures are lower than BASE-ENH on both axes.** The plan's own rule is that a run raising
rule count while narrowing file coverage has regressed; **here neither rose, which is a different
result and must not be dressed up as one.**

**You also have a control the plan was written without.** Phase 6 ran the *same* extractor at the
*same* settings over the *same* code a second time: 435 offers, of which only **158 merged on the
exact key** and **211 became candidates (48.5%)**. The corpus is saved at
`analysis/customer.ple.nng.app/knowledge/extracted-rules-4round-run2.json` and **is not ingested
into the real store**. Two consequences you should decide about early, in this order:

1. **The new extractor's run-to-run variance is now measurable**, which is the thing `PR-79` said no
   comparison could separate from the prompt change. The plan's mandatory noise floor is still
   BASE-ORIG-vs-BASE-ENH — run it, it is required — but **read it beside this one**, because the old
   floor mixes pipeline *and* merge-depth differences while this one mixes nothing.
2. **You may want a two-run NEW corpus as a second data point** (ingest run 2 for real, giving
   rule count and files-cited for a merged NEW). That is *available and reversible in one
   direction only*: see the gate below.

---

## ⚠ The one gate — decide BEFORE you ingest anything into the real store

**Ingesting run 2 into the real store destroys the 117-files-cited figure permanently.**
`gr_citation` has no `run_id`, and `_write_children` upserts on
`(gr_id, relative_path, start_line, end_line)`, so a merged run's citations attach to existing
requirements indistinguishably from the originals. The rule *count* survives
(`gr.first_seen_run_id` marks every row); **the file count does not.**

So: **take the 379/117-vs-470/148 comparison you want first, then decide about merging.** The merge
is reproducible from the saved corpus at any time; the single-run file count is not recoverable once
spent. Phase 6 was deliberately ingested into a scratchpad copy for exactly this reason — that
decision is in the plan's `Decision Log` and does not need re-litigating, but **it does not extend
to your session**: if you want a merged store, that is a fresh call and worth asking the user.

---

## Already verified with a reproducible probe — do not re-check

Measured 2026-09-10 and recorded in `Outcomes & Retrospective` → *Milestone 1.5 pre-flight*. This
list exists so you do not spend a pass on it.

| claim | probe |
|---|---|
| Both baseline files present, 838,585 B / 416,609 B | `ls` |
| BASE-ORIG = 55 `###` P0 cards + 760 catalog rows = **815** | section-boundary scan + row count |
| The catalog is **four** sub-tables; `grep -c '^\|'` gives **768**, minus 4 separators and 4 headers = 760 | ✓ |
| **Integrity check 2**: Summary − catalog per category = 17+30+7+1 = **55** | Summary is one line, **line 18** |
| BASE-ENH = **470** `####` cards, zero `###` headings | one parser suffices |
| **Neither baseline's citations carry a path prefix** — all 1,508 are code-root relative | full census of both files |
| `citations.parse_citation` handles both: 1,038 → 1,172 triples, 470 → 528, **0 strict rejections** | run over every capture |
| **109** BASE-ORIG citations are comma-separated range lists | the entry-11 class; `parse_citation` handles them |
| **47** BASE-ORIG citations are multi-FILE and `parse_citation` mis-parses them silently | shown against two examples |
| Layer census: BASE-ORIG is `ple-web` 500 / `ple-persistence` 216; BASE-ENH is `ple-services` 349; both cite `ple-model` 61 | top-level segment count |

---

## Traps that will each cost a cycle

- **The plan was wrong twice about the join key, and both statements are now struck.** It said the
  baselines' paths carry a `repos/nng-app-legacylift-analysis/` prefix and that you must reconcile
  `legacy/customer.ple.nng.app/`. **Neither is true. The join needs no path surgery.** Adding or
  stripping a prefix produces zero overlap, which the milestone's own rules warn "will look like a
  result." If you read an unstruck copy of either sentence, you are reading a stale checkout.
- **Do not write a third citation parser.** `citations.parse_citation` (strict mode) already parses
  both baselines with zero rejections and correctly expands the 109 multi-range citations. Import
  it.
- **But split multi-file citations BEFORE calling it.** 47 BASE-ORIG citations name two files in one
  string; `parse_citation` returns one triple whose path is everything up to the last colon and
  whose lines are the **second** file's. It is the same defect the plan records as fixed — that fix
  was to the *extractor prompt*, so it does nothing for a June baseline. Split on `;`, and on a
  comma only when the piece after it contains a `/` or a file extension (a comma is a *range*
  separator 109 times). Assert the split count.
- **1,038 captures ≠ 1,038 rule citations.** BASE-ORIG's P0 cards cite in prose as well as on the
  metadata line, so attribute captures to rules during the parse. Counting globally will not
  reproduce §S2.3's stated **327** distinct files for BASE-ORIG — and if your number disagrees with
  327, suspect your attribution before you suspect the spec.
- **Filter prose out of any file count on the NEW side too.** One `gr_citation.relative_path` is a
  445-character prose string that counts as a distinct path while naming no file. Filter on length
  or on `anchor_resolution` — this is why the frozen figure is 117 real files and not 118.
- **`legacylift-search` on `PATH` is broken.** Use `tools/legacylift_search/.venv/Scripts/`.
  `py -3.12` is not installed either.
- **From a worktree, that venv tests the MAIN checkout's branch** — set `PYTHONPATH=$PWD/src`.
- **Do not run `/modernize-assess`.** It re-authors `domains.json`, moves every `derived` subject
  and silently deletes the hand-added `vendored_globs` / `own_identities`. Settled.
- **The two baseline corpora and all six extraction corpora are untracked and unreproducible.**
  `.gitignore:92` and `:108` ignore the whole `repos/nng-app-legacylift-analysis/` tree. **Never
  overwrite one.** A cold-start agent on a fresh clone cannot run this milestone at all — if the
  files are absent, **stop and ask; do not reconstruct a baseline.**

---

## What SPEC-2 forbids you from writing — read §S2.4 before the write-up, not after

These are not stylistic preferences; the plan calls them mandatory and they are the reason the
milestone exists in this shape.

- **Neither baseline is ground truth.** Both are unvalidated model output over the same code. This
  measures **change and agreement, never accuracy.**
- **A higher rule count is not a better result.** 815 vs 470 over the same system, and the *smaller*
  set was judged the better run.
- **Never report NEW-ONLY as "rules gained" or BASE-ONLY as "rules lost."** They are
  discovery-or-hallucination and regression-or-correctly-dropped respectively, and telling which
  requires reading the cited code.
- **Every headline number must name its reference point** (229, 470 or 815) **and** whether the
  match was strict or tolerant. A number without both is not reportable.
- **Say the extractor's prompts changed, in the same breath as every headline number.** Both
  baselines are old-extractor output with no SPEC-1 notation, so no comparison here can separate a
  pipeline delta from a prompt delta. `PR-79`. This is disclosure, not a caveat to bury.
- **Report rule count and distinct-files-cited together, always.**

---

## Suggested first session

1. Confirm the two baseline files are on disk (the pre-flight table says they were at 2026-09-10).
2. Write the two parsers — BASE-ORIG needs two (P0 cards + four catalog sub-tables), BASE-ENH one —
   importing `parse_citation` and splitting multi-file citations first. **Gate each parser on the
   two integrity checks (815, and 55) before using its output for anything.**
3. Run the **noise floor**: BASE-ORIG vs BASE-ENH on the §S2.2 join key, strict and tolerant, with
   the four §S2.3 buckets. This is the bar every later delta is measured against.
4. Only then join NEW against each baseline.
5. Write it up under §S2.4's rules. **The write-up is the deliverable**, not the numbers.

**Model note:** the parsers and the join are mechanical and independently verifiable — good subagent
work (Sonnet 5). **The write-up and the interpretation are not** — every prior phase of this plan
that delegated interpretation had to re-derive it, and §S2.4's constraints are exactly the judgments
the plan warns against re-deriving. Keep step 5 in the main session.

---

## Not this milestone's job — leave filed

- `pending/deferred-small-items.md` entries 15, 16 and **17** (the last from Phase 6: the ingest
  banner's per-reason candidate tally cannot be reproduced from the store). Entry 17 needs no
  migration, so it is not blocked behind the four that do.
- `pending/dedupe-key-tier-mismatch.md` — now measured on two runs and larger than it looked, but
  altering the key is a re-key migration over a populated store.
- `pending/dto-catalog-bounding.md` — Phase 6 produced 117 `dataObjects`, and `ruleNames.slice(0, 250)`
  means `consumedBy` is incomplete again. A second confirmation of the defect, not a fix.
- The exported `requirements.jsonl` is still untracked. Committing client-derived requirements is
  the maintainer's call and no `git add -f` has been run.
- Milestones 2, 3 and 4. Milestone 4 is deferred to `pending/reqs-review-ui.md`.

---

## When this is done

Record everything in the plan's `Progress`, `Outcomes & Retrospective` and `Concrete Steps` —
**state stays in the plan; this file records nothing.** Then move this file to
`docs/exec-plans/completed/` with a `DISCHARGED` banner naming the commit, per
[`docs/exec-plan.md`](../../exec-plan.md) line 84.
