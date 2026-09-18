# Session Handoff — Milestone 1 Wave 3: review and verify Steps 1–2 (2026-09-01)

> **DISCHARGED 2026-09-01. This file is history; do not work from it.**
> Wave 3 ran. The adversarial review (`/code-review high` over the diff) raised four findings,
> `CR-08` … `CR-11`; every one was reproduced with an executable probe before being accepted, one
> (`CR-11`) was narrowed on probe, and all four were fixed in the same wave. Every §3 measurement
> was reproduced independently and none moved. **408 → 513 → 521 tests, exit 0.** The findings,
> the fixes and what the review confirmed correct now live in
> [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) → `Outcomes & Retrospective` →
> *Milestone 1 Steps 1–2*; the `CR-01` … `CR-06` rows in the *Milestone 0 code review* table above
> it now read **Fixed**.
>
> **Two corrections to what this document says**, recorded because they misdirect a reader who
> works from it anyway. §1's "**Nothing is committed**" was stale on arrival — Waves 1–2 had
> already landed as `05f8eaf8`, and the only dirty file was a concurrent session's `CLAUDE.md`.
> And §5's baseline of 513 is now 521.
>
> **Still open, and carried into the plan rather than left here:** Milestone 0's deferred
> acceptance criterion (no `legacylift-docs/` anywhere under `legacy/customer.ple.nng.app` after a
> real full `index` run) has **not** been discharged — it means re-embedding 15,040 chunks through
> Bedrock, and the plan still says to take it during Milestone 1's end-to-end run. No
> `busy_timeout` is set on either store; recorded in the retrospective as deliberately un-fixed.
> The next plan step is **Milestone 1 Step 3**.


**Your job:** run the review-and-verify wave over the **uncommitted** Milestone 1 Step 1 and Step 2
work now sitting in the working tree, then close out the wave. The implementation is done and the
suite is green; nothing is in flight.

The plan is [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md). Read its `### Step 1`
(~line 695) and `### Step 2` (~line 751) before reviewing anything — this document does **not**
restate the spec, only what happened and what to look at.

**Read §3 before you start.** Four implementation agents already ran, each with an executable-probe
standard, and several properties are measured rather than assumed. Re-verifying those wastes the
pass. §4 is where your value is highest: the seven places where an agent decided something the plan
did not specify.

---

## 1. State of the tree

Branch `feature/reqs-to-data-store`. **Nothing is committed.** Baseline was 408 tests; the tree is
now at **513 passing, exit 0**, verified independently of the agents that wrote it.

| Wave | Agent | Delivered | Tests |
|---|---|---|---|
| 1 | A1 (Opus) | `identity.py` + `tests/test_identity.py` — M1 Step 1 | 408 → 455 |
| 1 | A2 (Opus) | `CR-01`…`CR-06` + the §6 `--analysis-dir` gap | 455 → 487 |
| 2 | A3 (Sonnet) | `entity_class` declared at emission — Step 2, declaration half | 487 → 489 |
| 2 | A4 (Opus) | `INDEX_MIGRATIONS` v2, write path, `backfill-hashes` — Step 2, schema half | 489 → 513 |

Files changed: `cli.py`, `cli_helpers.py`, `config.py`, `domain_tagger.py`, `extractors.py`,
`indexer.py`, `migrations.py`, `models.py`, `profiles/extractors.json`, `store.py`,
`xml_extractor.py`, plus 12 test files. New: `identity.py`, `tests/test_identity.py`,
`tests/test_backfill_hashes.py`. Use `git diff` — this document does not duplicate it.

**Not ours, do not stage:** `CLAUDE.md` (modified) and `docs/exec-plans/pending/`
{`deferred-small-items.md`, `durable-loc-counts.md`, `embed-everything-evaluation.md`} come from a
concurrent session the user has since moved to a worktree; they were still present in this checkout
at handoff. **Stage selectively.**

---

## 2. What Wave 3 is

Two agents, as planned:

- **A5 — adversarial code review. Model: Opus.** Use the `code-review` skill at high effort, or
  `feature-dev:code-reviewer`. Scope: the full uncommitted diff. Report findings with
  `ReportFindings`.
- **A6 — suite, measurements, and failure triage. Model: Sonnet.** Runs the suite, triages any
  failure to a root cause and fixes trivially-scoped breakage (import paths, fixture drift) rather
  than only reporting it. Also re-checks the measurements in §3 and confirms the production
  databases are still untouched.

**The standard that matters, and the reason this wave exists:** all six Milestone 0 code-review
defects (`CR-01`…`CR-06`) were live while the full suite was green at 408 passing, exit 0. **A
passing suite is not evidence.** Every finding needs an executable probe that fails before the fix
and passes after. That standard was applied to the implementation waves; hold Wave 3 to it too.

---

## 3. Already measured — do not re-derive

Each of these was produced by an agent and, where noted, re-confirmed independently.

- **Production databases untouched.** All three real `index.sqlite` (ctcm-api, NNG app, ETSPii)
  still read `user_version 0` with 12 columns. Confirmed after Wave 2. All migration testing ran on
  scratchpad copies.
- **Migration v2 on copies of all three real indexes**: `user_version` 0→2 (0.02s / 0.86s / 2.81s),
  `anchor_key` non-NULL for every row, `content_hash` NULL for every row, `symbols`/`repo_files`/
  `chunks` counts unchanged, `ix_symbols_anchor_key` present with `unique=0`.
- **All 75,475 `anchor_key` values recomputed across the three copies: 0 mismatches.** This is the
  strong form of the insert-vs-backfill normalization check.
- **`backfill-hashes` drift case measured for real**: a line appended to the ETSPii stored-procedure
  file holding the most symbols → `files_drifted 1`, `symbols_hashed 580`, `symbols_skipped 9`, and
  exactly that file's 9 rows left NULL.
- **`extractors.json` counts match the plan exactly**: 52 entries, 36 distinct kinds, per-profile
  `csharp` 9 / `java` 7 / `python` 3 / `javascript` 7 / `typescript` 10 / `cobol` 8 / `sql` 8. No
  on-disk kind fell outside the plan's authoritative table.
- **`entity_class` distribution is plausible and `other` is well populated where predicted**:
  ETSPii `other` 265 (its largest kind is `fallback_definition`), NNG app `other` 1,471 (the
  `hibernate_*` / WebFlow open half).
- **`CR-01` verified end to end on a 232 MB copy** of the NNG app index: a plain `stats` read took
  it 0→1, and a Step-2-shaped `ALTER TABLE` applied through the read path took it 1→2 with 16,272
  symbols before and after.

---

## 4. Where your value is highest — decided by an agent, not by the plan

Seven judgement calls. None is known-wrong; each is a place where the plan was silent and an agent
chose. Review these before anything the plan already settled.

1. **`symbol_body_text`'s byte/line fallback — the largest unplanned change in Wave 2.**
   `xml_extractor.py:130` emits `end_byte == start_byte` **by construction** (it knows where an
   element starts in bytes, but start *and end* only in lines). That is every Hibernate mapping,
   Spring bean and WebFlow state — 1,739 of 16,272 NNG-app symbols were unhashable on the first
   real run. `symbol_body_text` now takes byte bounds only when they describe a real span and falls
   back to line bounds otherwise; after the fix, 16,272/16,272. Related subtlety to check:
   `store.SourceText.byte_space` is `text.encode()`, **not** raw file bytes, because extractors
   measure offsets against the re-encoded decoded text — slicing raw bytes would shift every offset
   in a file containing invalid UTF-8. **This is the piece to review first.**

2. **`CR-01` placement: migrations run from `SQLiteStore._connect`.** The consequence is stated
   plainly in a comment at the site: *a read command may now write to `index.sqlite`.* Guards: a DB
   newer than the build is refused outright, an unappliable migration raises naming both versions,
   and a fresh **table-less** DB is deliberately skipped (it gets its schema from `migrate()`, then
   is stamped) — that skip is load-bearing for v2. Worth adversarial attention: concurrent readers,
   read-only filesystems, and a user running `stats` against someone else's index.

3. **`Symbol.entity_class` was made required**, the `"other"` default removed, at a cost of 33 test
   fixtures across 5 files. Rationale: the *open* half of the `kind` domain is classified at
   framework-extractor sites no data-file test can reach, so a default silently absorbs an omission
   as `other` — and promoting a kind out of `other` later is an `ak2:` corpus-wide re-key. Check the
   33 fixtures were each given the class the shim would assign, not a convenient one.

4. **`is_default_setting()` folds backslashes before comparing paths.** The plan prescribed
   `Path(x) != Path(default)`; the agent found that insufficient, because on POSIX a backslash is an
   ordinary filename character, so the Windows hand-edit would not compare equal. This is a
   deliberate deviation from the plan text — confirm it is right and that it does not over-reach.

5. **`apply_path_overrides()` is now the single entry point for both flags**, with `resolve_paths`
   no longer short-circuiting. Settled precedence: `--index-dir` > `--analysis-dir` > manifest. Both
   documented narrowings must survive: the absolute-`index_dir` carve-out, and branch 2 winning when
   no override is given. Cross-family CLI probes exist; check they actually cross the family
   boundary (`index`/`search` vs `stats`/`symbols`/…).

6. **`anchor_key` raises `ValueError`** on an `entity_class` outside the closed set and on U+001F
   appearing in any input, and **`new_ulid` is monotonic within a millisecond** (increment rather
   than redraw, under a lock). Neither was specified. The U+001F rejection has a theoretical cost:
   adversarial client source carrying a control character in a qualified name aborts ingest rather
   than mis-keying. Step 3 owns `new_ulid`'s final format.

7. **The compatibility shim moved `identity.py` → `migrations.py`**, beside its single caller, with
   its 5 tests. This corrects an earlier brief that contradicted the plan's Step 1 and *Interfaces
   and Dependencies* sections. Its docstring keeps the deletability note; deleting it requires
   confirming every index in use got its columns from `migrate()`, not from this migration.

Also worth a look, lower priority: the reset guard's `allowed_ancestors` was widened to cover all
four resolver branches to make the `CR-06` parity comment true rather than softening it — check it
was not over-widened (three of the ten new tests are deliberate anti-over-widening guards). And
there is now a **structural** test asserting no module opens the index with a raw `sqlite3.connect`
(two-file allow-list), added because a functional test only covers today's call sites and a *new*
one is how `CR-01` arrived.

---

## 5. Open items Wave 3 should close or explicitly re-defer

- **Plan bookkeeping.** `Progress` checkboxes in the plan for Step 1, Step 2 and `CR-01`…`CR-06`
  are still unchecked. `Outcomes & Retrospective` needs a Milestone 1 Steps 1–2 entry. The `CR-01`
  …`CR-06` rows in the code-review table still read **Open**.
- **Stale counts.** `CLAUDE.md` still says 408 tests (stale before this work started, now 513) and
  still describes `CR-01` as gating Step 2. `tools/legacylift_search/README.md`'s Status section
  still reads "Wave 1 (skeleton)" and has no command reference in which to document
  `backfill-hashes`.
- **Milestone 0's deferred acceptance criterion**, still open and explicitly *not* covered by the M0
  parent checkbox: no `legacylift-docs/` directory anywhere under `legacy/customer.ple.nng.app`
  after a real full `index` run. It means re-embedding 15,040 chunks through Bedrock. The plan says
  to discharge it during Milestone 1's end-to-end run, which indexes that unit anyway. It has **not**
  been discharged.
- **Two index read paths were rerouted** (`domains` at `cli.py`, `DomainTagger.tag` at
  `domain_tagger.py`) to `SQLiteStore.connection()`. The sweep found no others in the package;
  `store.py:_connect` and `knowledge_store.py:_connect` are the allow-list. Hits outside the package
  are test files and generated client analysis artifacts under `repos/**/analysis/`.
- **After Wave 3**, the next plan step is **Milestone 1 Step 3** (the GR tables in
  `knowledge.sqlite`), which also settles `new_ulid`'s final identifier format.

---

## 6. Environment — read before running anything

- Python: `tools/legacylift_search/.venv/Scripts/python.exe`. **The `legacylift-search` shim on
  PATH is broken — use the venv binary.**
- Run tests from `tools/legacylift_search`: `.venv/Scripts/python.exe -m pytest -q`.
- **`pytest -q` in this project prints no summary line, only progress dots.** To count, use
  `--collect-only -q | tail` (which prints `tests/file.py: N` per file) — note that
  `grep -c "::"` on that output matches nothing and exits 1, which reads as a failure that is not
  one.
- **Baseline is 513 passing, exit 0.** Under 513 is a regression, not an environmental failure.
- Real databases live under `repos/nng-app-legacylift-analysis/analysis/<system>/` and
  `repos/ctcm/ctcm-api/legacylift-docs/`. **Never modify a production database** — copy to the
  session scratchpad first.
- `pyproject.toml` has no `[tool.ruff]` or `[tool.mypy]` section, so pytest is the only gate.

---

## 7. Suggested skills

- **`code-review`** — the primary tool for A5. Invoke as `/code-review high` (or `max`) against the
  working-tree diff. Pass `--fix` only after the findings have been read, not as part of the review
  run.
- **`security-review`** — optional and low-yield here; the diff is schema and path-resolution work
  with no new external input surface. Skip unless A5 surfaces something.
- **`claude-md-management:revise-claude-md`** — for the §5 stale-count cleanup in `CLAUDE.md`, once
  Wave 3's result is known. Do not run it before, or it will record a number that changes.
- **`code-simplifier`** — hold until after A5. Running it first churns the diff the reviewer is
  reading.

Do **not** run a further review round against the *plan document*. The plan's
`Surprises & Discoveries` gives a measured reason nine rounds were enough; Wave 3 reviews **code**,
which is a different series (`CR-`, not `PR-`).

---

## 8. Memory pointers

Relevant entries in the user's memory index (`MEMORY.md`):

- `legacylift-venv-aws-extra` — the 408 baseline (now superseded by 513 in this tree).
- `legacylift-knowledge-store-survives-reset` — **read the footer, the headline is inverted**;
  clearing `analysis/` now does destroy domain tagging.
- `m0-relocation-layout` — generated output lives under `analysis/<system>/`, not the client
  checkout.
- `reqs-to-data-store-interview` — plan history, the 125 `PR-` findings, and the `CR-` series.
- `sql-extractor-ssms-shape` — the standing lesson that hand-written fixtures miss the shape real
  corpora arrive in. Wave 2's `end_byte == start_byte` discovery (§4.1) is the same lesson again.

---

## 9. When this is discharged

Move this file to `docs/exec-plans/completed/` with a `DISCHARGED <date>` banner at the top, as
[`completed/SESSION-HANDOFF-m0-code-review-2026-09-01.md`](../completed/SESSION-HANDOFF-m0-code-review-2026-09-01.md)
does, and migrate anything still actionable into the plan rather than leaving it here.
