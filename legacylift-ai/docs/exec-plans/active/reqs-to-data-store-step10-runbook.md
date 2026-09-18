# Runbook: Milestone 1 Step 10 — the three mandatory measurements

**This file is a runbook, not a plan.** The plan is
[`reqs-to-data-store.md`](./reqs-to-data-store.md) in this directory and it remains the definitive
record of Milestone 1's state; this file held only the execution detail for Step 10, so that an agent
starting cold could run it without first reading 3,100 lines. **That step is now finished** — see the
banner — so this file is kept as the record of *how* it was run, not as work to do. Results live in
the plan (`Progress`, `Outcomes & Retrospective`, `Concrete Steps`), never here. Where this file and
the plan disagree, the plan wins and this file is the defect.

> ## ✅ STATUS 2026-09-10 — **DISCHARGED. All seven phases are DONE and Step 10 is complete.**
>
> **Do not run any part of this file again.** Every phase has been executed: the extraction ran
> twice (four rounds each, 437 and 435 rules), both corpora are saved and must never be overwritten,
> the three mandatory measurements are taken, `A1`/`A2`/`A3` are discharged, the merge acceptance
> test passes on the real store, and **Phase 6's `rules_candidate` = 211 of 435** is spent. `MEAS-1`
> was a once-only measurement on a first ingest into an empty store and cannot be retaken.
>
> **The plan is the record of what every phase produced** — `Progress`, `Outcomes & Retrospective`
> → *Step 10 Phase 3, as measured* / *Phase 4* / *Phase 5* / *Phase 6*, and the four matching
> `Concrete Steps` sections. This file was only ever the instructions, and §1's "Verified state"
> table describes the tree as it was before Phases 3–5, so several of its rows (store empty,
> `gr_run` 0, `index.sqlite` at `user_version` 0) are historical rather than current.
>
> **Milestone 1.5's frozen data point survived**, because Phase 6 was ingested into a scratchpad
> copy rather than the real store: the real store still holds run 1 alone — 379 requirements over
> 118 citation paths, 117 of them real files. The merged two-run store can be produced from
> `extracted-rules-4round-run2.json` whenever Milestone 1.5 wants it.
>
> **Next action lives in the plan, and it is Milestone 1.5.**

Written 2026-09-02. Every fact in the "Verified state" table below was measured on that date
against the working tree; **re-verify the table before you start**, because most of the rows are
things a single command can change.

---

## 0. What Step 10 actually is

Step 10 is **not a coding step**. Every line of Milestone 1's code is shipped (Steps 1–5, 6a, 6, 7,
8, 9). What remains is a real extraction run against the NNG app unit — hours of model time — and
the numbers taken from it.

It produces **three mandatory measurements**, and discharges **three other acceptance checks** that
no unit test can reach:

> **Naming, 2026-09-08.** These three were called `M1`/`M2`/`M3` until
> `feature/layer0-extraction-gap-detection` merged into this branch, at which point `M1`/`M2`/`M3`
> named *milestones* in `active/layer0-extraction-gap-detection.md` as well — two `active/` plans in
> one tree using one namespace for two unrelated things. They are `MEAS-n` here from now on; a
> bare `M1` in this repository means a milestone.

| # | Deliverable | Owner in the plan |
|---|---|---|
| MEAS-1 | Intra-run collapse rate on the first ingest into an empty store | Step 10, Step 6 |
| MEAS-2 | Count of rules that collapse into a decision table | Step 10 |
| MEAS-3 | Distribution of rule counts per candidate decision table | Step 10 |
| A1 | The extractor really emits `ruleClass` / `statement` / `modality` on live output | Step 6a |
| A2 | No `legacylift-docs/` anywhere under the client checkout after a real `index` run | Milestone 0, deliberately-open criterion |
| A3 | `PR-47`'s hand-off half: degraded ingest, then `reindex-vectors` populates the collection with no re-extraction | Step 5 / Step 6 |

Plus run metadata (`rounds_run`, `round_cap`, `stop_reason`, `new_rules_in_final_round`) surfaced by
`requirements stats`, and two unvalidated defaults that want measuring in this same run (section 8).

---

## 1. Verified state (measured 2026-09-02; coverage rows re-measured 2026-09-08 — re-verify before starting)

> **The 2026-09-08 coverage widening moved the file-set baselines in this table.** Rows marked
> *(pre-widening)* record what the CURRENT on-disk artifacts hold; the *(post-widening)* figure
> beside each is what Phase 1's rebuild will produce. Both are given deliberately — Phase 1's
> whole job is to move from one to the other, and a runbook that showed only one of them would
> read as either a stale table or an unexplained jump. The widening, its rationale and its
> measurements live in `active/layer0-extraction-gap-detection.md`
> (`Surprises & Discoveries` → *The 2026-09-08 coverage widening*, and the Decision Log).

| Thing | State | Consequence for this run |
|---|---|---|
| Branch | `feature/reqs-to-data-store`, clean | — |
| Test baseline | **1,250 passed, exit 0** (was 1,207 before the 2026-09-08 coverage widening added 43). Suite takes 13–20 min (6.5 min measured 2026-09-03) | Was 1,159 until `feature/layer0-extraction-gap-detection` merged in on 2026-09-03, adding 48 tests that are not this plan's. Below 1,250 is a regression you caused. `pytest -q` prints no summary line here — only dots; use `--collect-only -q` for a count |
| `analysis/customer.ple.nng.app/` | `PREFLIGHT.md`, `ASSESSMENT.md`, `domains.json`, `topology.json` present (Aug 3–4) | preflight / assess / map artifacts already exist under the M0 layout — see the decision in section 2 |
| `domains.json` | **12 domains, 45 `exclude_globs`**, plus **10 `vendored_globs` and `own_identities: ["nngco.com"]`** hand-added 2026-09-08 | current: it postdates the `excluded`-tier feature, so it is the canonical domain set. Do not casually re-author it — and note `/modernize-assess` authors NEITHER provenance field, so re-running it deletes them and puts 11 vendor `.tld` descriptors back into the index |
| `knowledge.sqlite` | `user_version` 1; **only** `domains`, `domain_edges`, `domain_exclusions`, `file_domains`. `file_domains` = **1,229 rows**, of which **383 `excluded`** *(pre-widening; the rebuild re-tags against 1,504 discovered files)* | the eleven GR tables + `gr_fts` do not exist yet and will be created free on first open by current code (Step 3's table-addition rule). `tag-domains` has already run with the current feature set |
| `index.sqlite` | **`user_version` 0**; `symbols` has **no `anchor_key`, `entity_class` or `content_hash`**; 16,272 symbols / 1,229 files; built Jul 23 *(pre-widening; post-widening discovery returns **1,504** files — `1,229 - 1 + 276`, the whole closed gap less one deliberately-excluded test Spring context)* | this index predates Step 2. Its migration can only backfill `entity_class` through the guessing shim, so **rebuild, do not backfill** |
| Embedding | Bedrock Titan `amazon.titan-embed-text-v2:0`, dim **1024**, `us-east-2`, `max_concurrency` 16, `embed_min_tokens` **80** | ~69% of chunks legitimately receive no vector, and the widening adds ~482 fallback chunks that will also be embedded — including `.properties` files carrying cleartext credentials, which therefore reach Bedrock (see the gap plan's Decision Log; the user accepted this). ~69% (a known `pending/embed-everything-evaluation.md` item, not a defect to fix here) |
| Bedrock creds | `AWS_BEARER_TOKEN_BEDROCK` + `AWS_REGION` set in `.claude/settings.local.json` `env` | probe them before committing to a rebuild (section 3, step 0c) |
| `legacylift-search` on `PATH` | **BROKEN** — resolves to `C:\Users\dnorton\AppData\Local\Programs\Python\Python314\Scripts\legacylift-search.exe` and dies with `ImportError` on `legacylift_search.cli` | **use `.venv/Scripts/legacylift-search.exe` for every command.** This is also why the extract-rules command file's step 2 will otherwise take its documented graceful-degradation branch and leave the store empty |
| Workflow launch quirks | non-ASCII in a workflow script fails the approval-dialog control-char guard; `args` arrives as a JSON **string**, not an object | launch from an ASCII-normalized copy in the scratchpad with an args shim (section 3, step 0b) |
| `semantic_top_k` / `semantic_distance_max` | 5 and 0.35, **kwargs on `ingest_extraction`, no CLI flag** | measuring them needs a Python harness, not a flag flip (section 8) |
| `hnsw:space` | **not set** by `ChromaVectorStore` — only `hnsw:sync_threshold` and `hnsw:batch_size` | the distance is whatever chromadb 1.5.9 defaults to (L2). Record this alongside any threshold number |

### Absolute paths

    REPO       C:\Users\dnorton\captechdev\legacylift-ai
    CLI        <REPO>\tools\legacylift_search
    PYTHON     <CLI>\.venv\Scripts\python.exe
    LLS        <CLI>\.venv\Scripts\legacylift-search.exe
    ANALYSIS   <REPO>\repos\nng-app-legacylift-analysis          <- the session cwd for slash commands
    CODE       <ANALYSIS>\legacy\customer.ple.nng.app            <- --repo-root for every CLI command
    OUT        <ANALYSIS>\analysis\customer.ple.nng.app
    DOMAINS    <OUT>\domains.json
    KNOWLEDGE  <OUT>\knowledge\knowledge.sqlite
    INDEX      <OUT>\index\code-search\index.sqlite
    RULESJSON  <OUT>\knowledge\extracted-rules-4round.json       <- the CORPUS OF RECORD (437 rules, 2026-09-10)

`<system>` is `customer.ple.nng.app` everywhere.

**These corpora are not in git.** `.gitignore:92` ignores `repos/nng-app-legacylift-analysis/`
entirely. A cold-start agent on a fresh clone cannot run this at all. If `CODE` is absent, stop and
ask — do not reconstruct anything.

**Never overwrite an extraction corpus; each is unreproducible.** `<OUT>\knowledge\` now holds
four, and a run saves to a NEW name: `extracted-rules-4round.json` (437 rules, the corpus of record),
`extracted-rules-round1.json` (133, the 1-round verification run),
`extracted-rules-round1-bodies-repaired.json` (the repaired-body merge of that one), and
`extracted-rules-scoped2round-test.json` (186, a scoped test artifact, deliberately not merged).
`extracted-rules-4round-journal-backup.jsonl` beside them is the workflow journal, one
`{"type":"result"}` line per agent — the recovery path if a run's return value is ever lost.

---

## 2. The one open decision — SETTLED 2026-09-08

The plan says "run the whole `code-modernization` pipeline, in this order, **and do not shortcut
it**" and lists four slash commands. Its stated *reason* is that each earlier step produces
something a later one needs. **All three earlier outputs already exist and are current** (rows 3–4
of the table above).

Re-running `/modernize-assess` re-authors `domains.json`, which is the pinned canonical domain set
that `subject` derivation reads through `file_domains`; a nondeterministic re-author moves every
`derived` subject and desynchronizes the Milestone 1.5 baseline.

**The user chose this on 2026-09-08:** re-run `/modernize-preflight` only (cheap, verifies the
environment), reuse the existing `ASSESSMENT.md`, `domains.json` and `topology.json`, and **disclose
the deviation explicitly in `Concrete Steps`** when you record the run. Milestone 1.5 compares
against this run, so that is the baseline.

The coverage widening (same date) makes the choice firmer than it was when written. `/modernize-assess`
authors `exclude_globs`, and re-running it now would re-author them around files the widening
deliberately brought *into* the index and around the extension-scoped exclusions settled in the gap
plan's Decision Log. **Do not run `/modernize-assess` on this unit without re-opening that decision.**

One consequence to carry into Phase 1: `domains.json` for both NNG units was hand-edited on
2026-09-08 to add `vendored_globs` and `own_identities`, which `discover_source_files` now reads for
third-party provenance. `/modernize-assess` does not author either field, so re-running it would
silently delete them and put 11 vendor `.tld` descriptors back into the index.

---

## 3. Phase 0 — pre-flight (~25 min, all three in parallel)

**0a. Baseline suite.** From `<CLI>`, in the background:

    .venv/Scripts/python.exe -m pytest -q

Expect **1,250 passed, exit 0** (1,207 before the 2026-09-08 coverage widening; 1,159 before the
2026-09-03 gap-detection merge). If
`tests/test_bedrock_embedder.py` fails, that *is* environmental
— install the declared extra: `.venv/Scripts/python.exe -m pip install -e ".[aws]"`. Any other
shortfall is a regression to bisect before continuing.
*No subagent — a background Bash call.*

**0b. Prepare the Workflow launch path.** Copy
`.claude/skills/code-modernization/workflows/extract-rules.js` to the scratchpad, replacing every
non-ASCII character (`--` for the em-dash, `->` for the arrow), and add the args shim at the top:

    const A = (typeof args === 'string' ? JSON.parse(args) : (args || {}))

then read `A.system` in place of `args.system`. Verify the copy has zero non-ASCII characters and
that `export const meta = {...}` is still a pure literal. **Leave the committed file untouched** —
agent types resolve globally, so the copy behaves identically.
*Subagent: **Sonnet 5**.*

**0c. Bedrock probe.** One embedding call through the configured provider, to confirm auth before
committing to a rebuild. Do not skip this — discovering a credential problem 40 minutes into an
index run wastes the whole run.
*Main session.*

---

## 4. Phase 1 — index rebuild and domain re-tag (~45–90 min). Discharges A2.

The rebuild and Milestone 0's open criterion are the same action, which is why they are one phase.

From `<CLI>`:

    .venv/Scripts/legacylift-search.exe index --reset --repo-root <CODE>
    .venv/Scripts/legacylift-search.exe backfill-hashes --repo-root <CODE>
    .venv/Scripts/legacylift-search.exe tag-domains --repo-root <CODE> --domains <DOMAINS>

`backfill-hashes` is a no-op on a freshly built index (which populates `content_hash` at extraction
time), so run it anyway rather than trying to remember which case you are in.

Then assert, before going further:

1. **No `legacylift-docs/` directory anywhere under `<CODE>`** — a filesystem assertion. **This is
   A2 and it must not be restated as "git status is clean"**: that checkout is not its own
   repository, `git rev-parse --show-toplevel` there returns this repository's root, and
   `.gitignore:92` ignores the whole tree, so the git form reports clean before and after
   regardless of what the code does.
2. The paths the commands **printed** resolve under `<OUT>` — check the printed paths rather than
   assuming which layout shape you are in.
3. Chunk and symbol counts match the pre-move transcript (16,272 symbols / 1,229 files is the old
   figure; a differing count is a finding to record, not silently accept).
4. `symbols.entity_class` is **non-NULL for every row**, including rows from the XML extractor and
   from the regex fallback. This is Step 2's acceptance check, and a rebuilt index is the only way
   to get classes the extractors actually declared.
5. `symbols.anchor_key` and `symbols.content_hash` fully populated.

**Do not delete `<OUT>` to "start clean."** Milestone 0's relocation inverted the old folklore:
`knowledge.sqlite` now lives *inside* `analysis/<system>/`, so deleting that directory destroys the
domain tagging **and every approved requirement with it**. What survives is narrower and precise:
`index --reset` cannot touch the knowledge store, because reset removes only the index subtree.

*Index run: main session, background. Verification queries: subagent, **Sonnet 5**.*

---

## 5. Phase 2 — the live extraction (hours; 10–40 agents). Discharges A1.

Launch the ASCII copy from 0b via the Workflow tool with `{system: "customer.ple.nng.app"}`. The
slash-command form is `/modernize-extract-rules customer.ple.nng.app` from a session whose working
directory is `<ANALYSIS>` (the directory holding `legacy/` and `analysis/`), **not** `<CLI>`.

**Do this in the main session.** The return value is hours of model time with exactly one copy;
losing it inside a subagent's context is unrecoverable.

**Step 1 of the calling-session work is to save the return value verbatim** to `<RULESJSON>`,
before anything else. Every later test in this plan replays that file.

Then run **A1, the pre-ingest shape check**, on the saved JSON:

- a rule object carries `ruleClass`, `statement` and `modality`;
- `pattern` is absent, `null`, or one of SPEC-1 §S1.4's ten values;
- `assumptions` and `implementationNotes` are present on **at least some** rules;
- `given` / `when` / `then` are **still there** alongside the notation fields.

**Check `implementationNotes` across the whole file, not on one rule.** It is legitimately absent
where the extractor abstracted nothing away, but empty on *every* rule of a real corpus means the
prompt instruction did not take. Cross-check that reading against the `V-STY-03` finding rate after
ingest — the two measure the same abstraction from opposite sides.

If the notation fields are missing, Step 6a's rewrite did not reach the run — most likely because
the agent definition or the Rule Card format still describes the old shape, since all three files
must change together. **Ingesting anyway fails on `statement NOT NULL`, which is correct behavior
and not a bug to route around.**

*Launch and save: main session. Shape check: subagent, **Sonnet 5**.*

---

## 6. Phase 3 — ingest #1 and the three measurements

From `<CLI>`. **Every command takes `--repo-root`**; on `ingest` it is load-bearing rather than
decoration, because ingest reads the repository three separate times: for the knowledge store's
location, for the cited line ranges each citation's span-level `content_hash` is computed over, and
for `index.sqlite` on the anchor resolution.

    .venv/Scripts/legacylift-search.exe requirements ingest --repo-root <CODE> --system customer.ple.nng.app --from <RULESJSON>
    .venv/Scripts/legacylift-search.exe requirements stats  --repo-root <CODE>
    .venv/Scripts/legacylift-search.exe requirements list   --repo-root <CODE> --state draft
    .venv/Scripts/legacylift-search.exe requirements list   --repo-root <CODE> --candidates

Notes that will otherwise cost a cycle:

- `--system` **overrides any `system` already in the payload, loudly**: `ingest_extraction` has no
  `system` parameter, it reads `payload["system"]`, so the flag injects into a shallow copy and a
  disagreement prints a stderr line naming both.
- An ingest that stores the rules but cannot reach an embedder **says so, names
  `requirements reindex-vectors` as the fix, and exits zero**. That is a healthy ingest.
- A failure is all-or-nothing: the SQLite half is one transaction, so a refused rule leaves no `gr`
  rows, no citations and no `gr_run` row. Fix the rule the error names by its `offer_ordinal` and
  re-run. There is no partial state and no resume flag.
- `requirements validate` **exits non-zero on a freshly ingested corpus, by design.** Findings are
  the human review queue, not a build failure.

> ### ⚠️ Phase 3 was REHEARSED on a copy on 2026-09-09 — read this before running it
>
> A full Phase 3 **and** Phase 4 ran against a scratch copy of `index/` + `knowledge/` via
> `--analysis-dir`. What that discharged, what it deliberately did not, and every number is in the
> ExecPlan's `Outcomes & Retrospective` → *Step 10 Phase 3 rehearsal, and the scoped two-round run*.
> Three things to carry into the real run:
>
> * **`MEAS-1` is unspent and the real store is still empty** (`gr` 0, `gr_run` 0). The rehearsal
>   figure was 8 offers / 4 distinct requirements. Do not quote it as the measurement.
> * **The merge acceptance test PASSED**, `MEAS-2` = 24 and `MEAS-3` says 19 of 24 tables sit at or
>   under six rules, so the replay-loop verdict is already reached.
> * **Copy `index/` too, not just `knowledge/`** if you rehearse again. A missing index is a
>   supported degraded success that exits zero, and every citation silently takes the file-level
>   anchor — which is exactly the number a rehearsal exists to check.
>
> The gate below still applies to the real run, and it passed in the rehearsal (`derived`=133).

### Gate before going further

`stats` must report a **non-zero count of `derived` subjects**. If every subject is `llm_named`,
`tag-domains` did not run or matched nothing, and the run is not testing what Step 3 built. Stop and
fix that before taking any measurement.

### MEAS-1 — intra-run collapse on first ingest into an empty store

`KnowledgeStore.intra_run_collapse_count(run_id)`, surfaced in block 5 of `requirements stats`:

```sql
SELECT COALESCE(SUM(n), 0) FROM (
  SELECT COUNT(*) AS n FROM gr_run_hit WHERE run_id = ? GROUP BY gr_id HAVING COUNT(*) > 1
);
```

**It counts offers, not collapsed requirements.** Two offers landing on one `gr_id` returns 2, not
1 — the question is how many mined rules lost their own row. Its own docstring says so, but "the
intra-run collapse count" reads like a count of collapses, and one of Step 10's three measurements
is exactly this number. **Report both readings and label which is which.** The count of distinct
`gr_id`s that absorbed more than one offer is the other reading:

```sql
SELECT COUNT(*) FROM (
  SELECT gr_id FROM gr_run_hit WHERE run_id = ? GROUP BY gr_id HAVING COUNT(*) > 1
);
```

A false-same is invisible by construction, so this figure is the only evidence available about it.
**If it comes back large: say so plainly, treat every coverage claim from the store as provisional
until the key is strengthened, and do not proceed to Milestone 1.5's comparison as though the corpus
were complete.**

### MEAS-2 — rules that collapse into a decision table

```sql
SELECT COUNT(*) FROM gr WHERE structured_body_type = 'decision_table';
```

Not surfaced by `stats`; take it directly.

### MEAS-3 — distribution of rule counts per candidate table

`len(structured_body.rules)` over those rows — `rules` being DMN 1.5's own list of decision rules,
so the number means what the study below means by it. `structured_body` is JSON in a `TEXT` column:

```python
import json, sqlite3
conn = sqlite3.connect("file:<KNOWLEDGE>?mode=ro", uri=True)
counts = [len(json.loads(b)["rules"])
          for (b,) in conn.execute(
              "SELECT structured_body FROM gr "
              "WHERE structured_body_type = 'decision_table' AND structured_body IS NOT NULL")]
```

**The verdict this feeds.** The argument for DMN-shaped tables is that such a table is *executable*,
so the legacy system can serve as an oracle for the decision-logic subset. But the only published
code-to-DMN study reports zero-percent decision-rule accuracy on three of its eight logic cases,
collapsing past roughly six rules per table, on hand-picked single-file Java of at most nineteen
rules. **So if most candidate tables in this corpus exceed about six rules, the replay loop waits.**
Frame the loop as a *detector of bad extraction* rather than a validation of good extraction — that
makes it more valuable, not less, because it is the only place in the design where extraction error
is measurable rather than assumed. **Do not promise DMN coverage of the corpus.**

### Run metadata, and the rest of what this run is the only chance to record

From `gr_run`: `rounds_run`, `round_cap`, `stop_reason`, `new_rules_in_final_round`. All four now
have a producer — `extract-rules.js` emits `roundCap`, `stopReason` and `newRulesInFinalRound` in
the camelCase spellings `gr_ingest` already read. `stats` prints **`unmeasured`** for a NULL rather
than `0`, because `0` would invent a termination record. `stop_reason` is one of `dry`, `round_cap`,
`budget_exhausted`; the third comes from the extraction loop's in-loop token-budget `break`.

Also record, from the same run: cumulative distinct-files-cited across all runs, the `gr_run` count
identity from Step 3, the `V-STY-03` finding rate (cross-checked against the `implementationNotes`
reading above), the anchor-resolution breakdown, the SME-field fill rates, and that the data-flow
block reports **no entries, names both reasons in words, and prints no rate** — a percentage over an
empty table is the defect, not the expected value (Step 7).

*SQL and tabulation: subagent, **Sonnet 5**. The three verdicts and the labelling call: **main
session, Opus 5** — these are the judgments that can invalidate Milestone 1.5.*

---

## 7. Phase 4 — the merge acceptance test (headline pass/fail)

Re-ingest **the same saved JSON file**, not a second extraction:

    .venv/Scripts/legacylift-search.exe requirements ingest --repo-root <CODE> --system customer.ple.nng.app --from <RULESJSON>

Then assert:

- `gr`, `gr_citation`, `gr_scenario` and `gr_edge_case` counts are **all identical** to run 1. All
  four are named because a flat requirement count over any growing child table is the same bug one
  level down, and `gr_scenario` is the largest of them.
- `gr_run` gains a second row whose `rules_merged` equals run 1's `rules_in`.

This is stated against a fixed input on purpose. It is a hard pass/fail and it is the single most
important observable outcome in this plan.

*Subagent: **Sonnet 5**.*

---

## 8. Phase 5 — A3, plus the two unvalidated defaults

### A3 — `PR-47`'s hand-off half

Against a **copy** of `<KNOWLEDGE>`, so the real store is not disturbed: ingest with no reachable
embedder (must exit **zero**, and must name `requirements reindex-vectors` as the fix), then

    .venv/Scripts/legacylift-search.exe requirements reindex-vectors --repo-root <CODE>

and confirm the `gr_statements` collection is populated **with no re-extraction**. This spans two
command modules, which is why it was not provable at unit scale.

**Three traps, all measured, all of which have cost a cycle here:**

1. The `hash` embedding provider is built at `manifest.embedding.dimension` = **1024**, not
   `HashEmbedder`'s own default of 64. A collection seeded at 64 fails `validate_dimension` and the
   test then measures a dimension mismatch instead of what it claims.
2. `EmbeddingConfig.provider` defaults to **`qwen3`** — a model load. Any test or dry run touching
   the vector half must pin `hash` explicitly.
3. `open_gr_collection` resolves the collection from `store.sqlite_path.parent`, so the collection
   lives under the **knowledge** directory (`analysis/<system>/knowledge/chroma`), never the index
   directory. Being out of `index --reset`'s reach is the entire reason for that location. Do not
   pass an index directory.

### The two unvalidated defaults, and the unpinned metric

`SEMANTIC_TOP_K = 5` and `SEMANTIC_DISTANCE_MAX = 0.35` (`gr_ingest.py`) are **kwargs on
`ingest_extraction` with no CLI flag**, so measuring them means a Python harness that re-runs stage
two against the ingested store at several values — not a flag flip.

Neither can ever cause a merge; they only change which pairs a reviewer is shown, so getting them
wrong can never cause a false-same. **The failure direction is the quiet one:** too tight a
threshold raises fewer candidates, and stage two returning none is indistinguishable from there
being no near-duplicates to find.

**Both are metric-dependent and nothing pins the metric.** `ChromaVectorStore` sets
`hnsw:sync_threshold` and `hnsw:batch_size` but no `hnsw:space`, so the distance is whatever the
installed chromadb defaults to — L2 on the pinned 1.5.9. Record that fact next to any threshold
number you report; `pending/deferred-small-items.md` already carries "no collection pins its vector
distance metric" as an entry.

*Subagent: **Sonnet 5**, with the three traps stated verbatim in the prompt. Escalate to Opus 5 if
it stalls.*

---

## 9. Phase 6 — second live extraction — **DONE 2026-09-10, do not re-run** (see the status banner)

Only after Step 10 is recorded. Run the extraction itself a second time and expect a different
shape: mostly `merged`, some `candidate`, a few `new`. Record `rules_new`, `rules_merged` and
`rules_candidate`.

> **SETTLED 2026-09-10 — ingest Phase 6 into a COPY of the store, not the real one.** The reasoning
> is in the plan's `Decision Log`; do not re-litigate it here. `rules_candidate` needs only a store
> that already holds run 1, which a copy has, and ingesting for real would decide Milestone 1.5's
> framing as a side effect by destroying its distinct-files-cited figure (`gr_citation` has no
> `run_id`). The merged store can be produced later from the same saved corpus.
>
> Build the copy under the scratchpad and pass `--analysis-dir`, as Phase 5 did:
>
>     <scratch>/p6/index/code-search/index.sqlite        <- copy (227 MB)
>     <scratch>/p6/index/code-search/manifest.snapshot.json
>     <scratch>/p6/knowledge/knowledge.sqlite            <- copy AS IS; do NOT empty the gr tables
>     <scratch>/p6/knowledge/chroma/                     <- copy TOO (6.7 MB)
>
> **Copying `chroma/` is load-bearing and is the one difference from the Phase 5 recipe.** Phase 5
> deliberately let the collection rebuild; Phase 6 must not. The collection holds the 379 vectors
> that make this **the first ingest able to exercise stage two's semantic half at all** — a first
> ingest queries an empty collection and a re-ingest never reaches stage two. Omit `chroma/` and the
> collection starts empty, reproducing exactly the blindness the run exists to escape.
>
> **Assert before ingesting**: `requirements stats --analysis-dir <scratch>/p6` must report
> `gr_statements holds 379 of 379` and `gr` 379. If it reports a shortfall, the copy is wrong and the
> semantic-half observation is void. Then watch `merge candidates raised` for a **`semantic`** reason
> with a non-NULL `similarity` — all 148 candidates in the store today are `drift` (85) or
> `range_overlap` (63), so one would be the first ever produced. Phase 5's harness predicts roughly
> 18 at the default `SEMANTIC_DISTANCE_MAX = 0.35`; **zero is worth investigating, not shrugging at.**

`rules_candidate` is **Step 6's key-instability measurement** — how much the extractor's `ruleClass`
and `pattern` moved between two runs over identical code. A non-zero `rules_new` is not a merge
defect; treat it as one only if the same rules also fail to appear in
`requirements list --candidates`.

This is a softer criterion than Phase 4 on purpose: the extractor is a language model and its output
is not reproducible, so asserting a flat count across two live extractions would make the
milestone's central test fail for a reason that has nothing to do with the store. Run it after
Step 10 is recorded so a noisy second run cannot hold up the milestone.

---

## 10. Phase 7 — record the results — **DONE 2026-09-10, do not re-run** (see the status banner)

In `reqs-to-data-store.md`:

- **`Progress`** — tick Milestone 1 step 10; move the **Next action** to Milestone 1.5; update the
  test baseline if it moved; tick Milestone 0's deliberately-open sub-criterion (A2) and note where
  Step 6a's live check (A1) was discharged.
- **`Outcomes & Retrospective`** — a new *Milestone 1 Step 10* entry carrying all three
  measurements **with their labels and their verdicts**, the run metadata, the A3 result, the
  threshold findings from section 8, and the `rules_candidate` figure once Phase 6 has run.
- **`Concrete Steps`** — the exact commands run and short transcripts, plus the section-2 decision
  and its disclosure.
- **`Surprises & Discoveries`** — anything the run contradicted. Note that every `file.py:NNN`
  reference in the plan is already known stale; do not re-file that.
- `pending/deferred-small-items.md` — append rather than burying a small discovery in a plan's
  *Surprises* section. It holds six entries today and four of them want the same first
  `knowledge.sqlite` *column* migration.

Commit on `feature/reqs-to-data-store`.

*Subagent: **Opus 5** — the plan is the definitive record of its own state and the wording is
load-bearing.*

---

## 11. Delegation summary

| Work | Where | Model |
|---|---|---|
| 0a baseline suite | main session, background Bash | — |
| 0b ASCII copy + args shim | subagent | Sonnet 5 |
| 0c Bedrock probe | main session | — |
| Phase 1 index rebuild | main session, background | — |
| Phase 1 post-rebuild assertions | subagent | Sonnet 5 |
| Phase 2 workflow launch + saving `<RULESJSON>` | **main session only** | — |
| Phase 2 A1 shape check | subagent | Sonnet 5 |
| Phase 3 SQL and tabulation | subagent | Sonnet 5 |
| Phase 3 verdicts and labelling | **main session** | Opus 5 |
| Phase 4 merge acceptance | subagent | Sonnet 5 |
| Phase 5 A3 + threshold sweep | subagent (traps stated verbatim) | Sonnet 5 |
| Phase 7 plan-document updates | subagent | Opus 5 |

Nothing in Phase 2's launch or Phase 3's interpretation is delegated: the extraction return value is
hours of model time with one copy, and the three verdicts are exactly the judgments the plan warns
against re-deriving. Everything mechanical and independently verifiable goes to Sonnet 5; the two
document-writing tasks go to Opus 5.
