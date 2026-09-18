# SESSION HANDOFF — spend MEAS-1 (Step 10 Phase 3) — 2026-09-10

> **DISCHARGED 2026-09-10. This file is history; do not work from it.**
> The user authorized the spend and **`MEAS-1` was spent**: the four-round corpus ingested into the
> empty store as `RUN-01M2646H97JAZJPPKHSCZT1RRY`, exit 0, 437 offers → 379 rows. All three
> mandatory measurements were taken (`MEAS-1` = 106 offers / 48 rows, verdict **true-same**;
> `MEAS-2` = 39; `MEAS-3` = 3–8 rules per table, median 5, 84.6% at or under six) along with all
> four `gr_run` metadata columns. Two of this file's four "not verified" items are closed by
> observation: the bad citation **degrades rather than blocks** (rule 254 stored with 4 `unresolved`
> anchors, the only row with zero resolved citations), and `export` **does** trip the completeness
> gate (refuses, exit 1; `--allow-incomplete` writes the `_incomplete` header). Item 4 — whether a
> `MEAS-1` redo is possible — is now moot, and item 5 held (`gr_dataflow` 0, reported in words with
> no rate).
>
> One thing this file did not predict was found and is **not a defect**: 34
> `dedupe_key_anchor_only` clusters hold 54 excess rows, and all 34 have every internal pair queued
> as a `drift` merge candidate, so the under-merge residue is fully visible. The mechanism —
> mixed body/bodyless clusters being discriminated at different tiers, so the exact key can never
> match them — is now `pending/dedupe-key-tier-mismatch.md`.
>
> Everything durable is in [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md):
> `Progress` (rewritten, with the next action now **Phase 4**), `Outcomes & Retrospective` →
> *Step 10 Phase 3, as measured*, and `Concrete Steps` → *Step 10 Phase 3, as actually run*.
> **Phases 4, 5 and 6 remain**, and the runbook `active/reqs-to-data-store-step10-runbook.md` §7–§9
> is still live for them.
>
> **One decision left open deliberately, and it is the maintainer's**: the export wrote
> `knowledge/requirements.jsonl` (380 lines, 2.5 MB) but `.gitignore:108` ignores the whole
> `repos/nng-app-legacylift-analysis/` tree, so it is untracked. No `git add -f` was run. The
> 437-rule corpus and its ingested form still exist only on one laptop.

---

**Everything below is the original handoff, kept verbatim as history.**

---

**Disposable.** Durable facts are already in
[`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) and
[`active/reqs-to-data-store-step10-runbook.md`](../active/reqs-to-data-store-step10-runbook.md). This file
says only what to do next and what not to waste a pass on. If you find yourself wanting to write a
measurement or decision here, put it in the plan instead.

Branch `feature/reqs-to-data-store`, HEAD **`ba8907d4`**, tree clean, nothing pushed.

---

## The job

Run **Phase 3** of the runbook (§6) against the four-round corpus, which now exists: ingest it into
the empty store, take `MEAS-1` in **both readings**, then `MEAS-2`/`MEAS-3` and the four `gr_run`
metadata columns. Then Phase 4 (merge acceptance test) and Phase 5 (`A3`).

Read in this order — do not start from this handoff alone:

1. `reqs-to-data-store.md` → `Progress` (the Next action) — the definitive state.
2. The same plan's `Surprises & Discoveries` → *What the four-round run discovered (2026-09-10)*.
3. `reqs-to-data-store-step10-runbook.md` **§6**, which carries the exact commands, both `MEAS-1`
   SQL readings, the `derived`-subjects gate that must pass first, and the path table.

Corpus: `<OUT>/knowledge/extracted-rules-4round.json` — 437 rules. The runbook's `RULESJSON` now
names it.

---

## ⚠ Do not ingest without confirming with the user first

**This was discussed at length this session and NOT authorized.** The user asked what spending
`MEAS-1` means and confirmed they want the corpus preserved going forward; they did not say to
proceed. Treat the go-ahead as still outstanding.

Why it matters: `MEAS-1` is defined as the intra-run collapse on the **first** ingest into an
**empty** store, no `requirements` subcommand can empty the store (checked — all fourteen), and
`index --reset` cannot reach it. The store is empty on purpose today (`gr` 0, `gr_run` 0). The plan's
`Progress` states this as the one live decision and marks it the user's call.

Two things the user was told, both verified, so do not re-litigate them:

- **Ingest does not consume the corpus.** `cli_requirements/run_cmds.py:162` is
  `from_path.read_text(...)`; an audit of the whole package for write-mode `open`/`unlink`/`rename`/
  `write_text`/`shutil` against the source found nothing.
- **Ingest is what makes the corpus durable.** `requirements export` writes the git-committable
  JSONL that is the real backup (its own docstring says so); the tree is gitignored, so today the
  437 rules exist only as untracked files. The sequence that ends that exposure is
  **ingest → export → commit the JSONL**.

---

## Already verified with a reproducible probe — do not re-check

All against `<OUT>/knowledge/extracted-rules-4round.json`. Numbers and interpretation are in the
plan's `Outcomes & Retrospective` → *Step 10 Phase 2, the four-round run*; this list exists so you
don't spend a pass reproducing them.

| claim | probe |
|---|---|
| `A1` passes 437/437, all four checks; `implementationNotes`/`assumptions` 100% | shape walk over `confirmedRules` |
| **88/88 `structuredBody` payloads valid** — no repair pass needed | `gr_body_schemas.validate_structured_body(t, body)` per rule |
| 441 citation triples, 0 parse errors, 0 whole-file sentinels, 0 past-EOF ranges | `citations.parse_citation` per `source` |
| 437 of 441 triples resolve; the 4 failures are all rule index **254** | `(codeRoot / path).is_file()` per triple |
| store empty (`gr` 0, `gr_run` 0), `file_domains` 1,504 | `sqlite3` counts |
| `DTO_SCHEMA` is 543 B, second-smallest of five schemas | brace-match + `JSON.stringify` in `node` |
| `consumedBy` truncation is real: 247 distinct rules named, all inside the first 250, **0 of the 187 beyond** | split `confirmedRules` names at 250, intersect |

**Recipes that lived only in a session scratchpad and are now gone.** Two are worth keeping because
they are pure functions of a saved corpus, so they are unit tests rather than runs:

- *Body validity*: load `confirmedRules`, for each rule with a non-null `structuredBody` call
  `validate_structured_body(rule["structuredBodyType"], rule["structuredBody"])` and bucket by type.
  Also assert no body without a type and no type without a body.
- *Citation resolvability*: for each rule, `parse_citation(rule["source"])` → triples; count those
  whose `codeRoot / path` is not a file; separately flag `end == WHOLE_FILE_END_LINE` and
  `end > len(open(file).readlines())`.

Run the suite from `tools/legacylift_search` as `.venv/Scripts/python.exe -m pytest` (bare `-m
pytest`; `pyproject` sets `addopts="-q"`). **The suite was not re-run this session** — no code
changed, only docs. Baseline stands at **1,263 passed, exit 0** per the plan.

---

## Not verified — this is where your value is highest

1. **`MEAS-1` itself.** Unspent. Both readings are required and must be labelled; the runbook §6
   gives the two queries and says why the distinction matters.
2. **Whether the one bad citation degrades or blocks ingest.** Rule 254
   (`Northern Natural Gas own-party identity`) has a prose `source` whose 4 triples all fail to
   resolve. Expectation is a degraded `unresolved` anchor, not an abort — **not observed**. It is
   the first rule in any corpus with *zero* resolvable citations, so the "unresolved" path may never
   have run on a rule like this. Watch the anchor-resolution breakdown. Defect is
   `pending/deferred-small-items.md` entry 13.
3. **Whether `export` trips the completeness gate.** Predicted yes — `stopReason` is `round_cap`
   with 14,925 chunks unaccounted for, one of the two reasons the gate names — so the durable backup
   likely needs `--allow-incomplete`, which writes an `_incomplete` header naming the run and reason.
   Untested.
4. **Whether a redo of `MEAS-1` is actually possible.** Deleting `knowledge.sqlite` by hand would
   also drop `file_domains` (1,504), `domains`, `domain_edges`, `domain_exclusions`.
   `tag-domains` plus `requirements rederive-subjects` *looks* like a recovery path, but **whether
   `tag-domains` is deterministic given an unchanged `domains.json` was not established.** Do not
   present a redo as safe on the strength of this handoff.
5. **`gr_dataflow` stays empty** — Step 7 shipped with no writer, gated on the search plan's
   Milestone 26. Expect 0 rows; that is not a Phase 3 defect.

---

## Traps that have each cost a cycle

Every one of these is recorded in the plan or runbook; listed here only as a checklist.

- **`legacylift-search` on `PATH` is broken.** Use `tools/legacylift_search/.venv/Scripts/`.
  `py -3.12` is not installed either.
- **`--repo-root` is load-bearing on `ingest`**, not decoration — it is read three times (store
  location, cited line ranges for span hashes, `index.sqlite` for anchor resolution). Runbook §6.
- **Do not run `/modernize-assess`.** It re-authors `domains.json`, moves every `derived` subject,
  desynchronizes the Milestone 1.5 baseline, and silently deletes the hand-added `vendored_globs` /
  `own_identities`. The `/modernize-preflight`-only deviation is settled — runbook §2.
- **Never overwrite an extraction corpus.** Four exist plus a journal backup; the runbook's path
  section now lists them and their provenance. All are untracked and unreproducible.
- **The `derived`-subjects gate runs before any measurement.** If every subject is `llm_named`,
  `tag-domains` did not take and the run is not testing what Step 3 built.
- Bedrock credentials are in `.claude/settings.local.json` under `env` (key names only:
  `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`) — do not echo values into a transcript.

---

## Suggested skills

**None is required to run Phase 3.** It is CLI commands and SQL from the runbook; reaching for a
skill here adds indirection, not leverage.

- **`code-modernization:repair-structured-bodies` — do NOT invoke.** All 88 bodies validate. It
  exists for a corpus whose payloads `validate_structured_body` rejects, which is not this one.
  Named explicitly because the plan's history makes it a tempting reflex.
- **`code-modernization:modernize-extract-rules` — do NOT invoke.** Phase 2 is complete. A fresh
  launch re-spends hours and `resumeFromRunId` is dead for both prior runs (prompt fixes landed
  after them, so no agent replays from cache).
- **`/code-review`** — only if Phase 3 produces code changes. The plan's `CR-` series is the record
  of prior rounds; its `Surprises & Discoveries` explains why the *plan document* is closed to
  further review rounds.
- For delegation, use the runbook's own per-phase subagent/model split (§11) rather than improvising
  one. Phase 3's launch-and-record work belongs in the **main session** — the runbook's rule about
  hours-of-model-time artifacts applies to the measurements too.

---

## If Phase 3 goes well

Phases 4 and 5 follow directly (runbook §7–§8): the merge acceptance test — **the plan's single most
important observable outcome**, already PASS in rehearsal against a copy — and `A3`, `PR-47`'s
hand-off half. Then Phase 6, and record everything in the plan's `Progress`,
`Outcomes & Retrospective` and `Concrete Steps`. **State stays in the plan; the runbook records
nothing.** When this handoff's work is done, move it to `docs/exec-plans/completed/` with a
`DISCHARGED` banner naming the commit, per `docs/exec-plan.md:84`.
