# Test Plan — Domain Enhancements at Scale via a Full Modernize Run on the NNG App

**Status:** ✅ **EXECUTED 2026-07-23 — all applicable Done-when conditions met (verified against
artifacts 2026-07-30).** Authored 2026-07-21. Governed a real-repo, at-scale test of the
capability-domains feature shipped on branch `feature/domains-enhancement` (since merged into
`feature/version-next`; the branch no longer exists).

**Result:** M1–M8 + the #57 probe all PASS — 24 PASS, **0 FAIL**. Report:
`repos/nng-app-legacylift-analysis/analysis-domains-enhanced/DOMAIN-ENHANCEMENTS-TEST-REPORT.md`
("No milestone failed"). Deliverables present for both units; `knowledge.sqlite` exists per unit.
Stage E (extract-rules) was **deliberately deferred**, which forfeits no milestone (§9 item 4 is N/A)
— it remains the one thing in this plan never run, still gated on the pending extract-rules changes.

**Two post-run supersessions** (the plan text below is the dated 2026-07-21 record and is *not*
rewritten to match):
- **2026-07-24 — `exclude_globs`.** The excluded-by-design tier shipped (`98f2f9bf`) and
  `/modernize-assess` was taught to author `exclude_globs` (`dec5b809`). The APP's "41% unassigned"
  finding in §M2/§M4 of the report is superseded: authoritative APP state is now
  `coverage 100% · 0 unassigned · 383 excluded`.
- **2026-07-30 — DB SQL extractor.** §8's "DB-unit domains" risk note and the report's
  "SQL extractor edge resolution" at-scale observation are **resolved** (ExecPlan
  `docs/exec-plans/completed/sql-extractor-temp-cte-fk.md`, `1efd49a9`). The DB unit was re-indexed
  and its Stage D map re-run off the index graph instead of the grep fallback. **Consequence for the
  artifacts below:** `analysis-domains-enhanced/customer.ple.nng.db.ETSPii/` still holds the
  *2026-07-23* snapshot; the current DB map lives in
  `analysis/customer.ple.nng.db.ETSPii/`. Re-run Stage F for that unit if the enhanced folder should
  carry the corrected map.

**Self-contained:** everything needed to execute is in this file. No need to re-read the source
plan, but the feature it tests is `docs/exec-plans/completed/domain-enhancements-plan.md`
(milestones M1–M8).

---

## 1. Context / Why

`feature/domains-enhancement` shipped the 8-milestone capability-domains feature: a durable
`knowledge.sqlite`, the `tag-domains` / `domains` / `render-architecture` CLI verbs, a
`--domain` filter on `search`, a `validate` domain-freshness axis, indexer 7-Auto
self-tagging, and per-domain `stats`. That feature was validated **only** against the tiny
`tests/fixtures/polyglot_repo` fixture; at-scale validation on a real repository was explicitly
deferred (see the source plan's "Validation and Acceptance" §). **This plan is that deferred
at-scale test.**

We run the enhancements the way they are intended to be used — inside a **full modernize
pipeline** — against the NNG legacy application, and produce a domain-enhanced analysis plus a
milestone-by-milestone test report.

**Target:** `repos/nng-app-legacylift-analysis/legacy/` — two units:
- `customer.ple.nng.app` — Spring Boot 2.7.5 / Spring WebFlow / Hibernate 3.3.2 monolith,
  ~97k Java LOC across 6 Gradle modules, 995 Java files + 364 JSP + 399 XML + 133 `.hbm.xml`
  + SQL. **Has a manifest** (`semantic-search.manifest.json`, already Bedrock-configured).
- `customer.ple.nng.db.ETSPii` — SQL database project, ~618 `.sql` files. **No manifest — must
  be created (Phase 0).**

**Output:** everything into `repos/nng-app-legacylift-analysis/analysis-domains-enhanced/`
(currently empty). Two sibling baselines already exist for comparison:
- `analysis-original/` — pre-enhancement `/modernize-assess` output (has the LLM hand-authored
  `ARCHITECTURE.mmd` and a 10-domain markdown table in `ASSESSMENT.md`).
- `analysis-semantic-search-enhanced/` — the prior semantic-search-enhanced comparison run.

**User decisions locked in (2026-07-21):**
1. Embeddings: **full re-chunk + re-embed + graph extraction, real Bedrock Titan** (NOT hash,
   NOT reuse of the stale Jul-2 index).
2. Domain source: **run the full process new** — preflight → assess → map → extract; assess
   emits `domains.json` live (true M3 test).
3. Extract: use the **current 4-round cap, then stop and post a status update** (do not loop).
4. Scope: **both units** — the Java app and the ETSPii DB project.

**Update (2026-07-23):** Stage E (extract-rules) is now **deferred** — decision 3 applies only
when it is eventually run. Rationale: extract-rules consumes no domain-enhancement surface, so
every milestone (M1–M8) and the #57 probe is determinable by the end of Stage D (map), and
extract-rules changes are pending. See the Stage E section. This run is **preflight → assess →
tag-domains → map, then stop.**

Out of scope (not requested): `modernize-harden`, `-transform`, `-uplift`, `-reimagine`.

---

## 2. Environment facts (verified 2026-07-21)

- Python: `py -3.12` (3.12.9) works; `legacylift_search` imports OK.
- The `legacylift-search` CLI already exposes `tag-domains`, `domains`, `render-architecture`,
  plus `search`/`validate`/`stats`.
- App manifest embedding block (already correct — no CLI override needed):
  `provider: "api"`, `model: amazon.titan-embed-text-v2:0`, `dimension: 1024`,
  `region: us-east-2`, `max_concurrency: 16`, `normalize: true`.
- App manifest `include_globs` already cover `.java`, `.sql`, `.hbm.xml`, `*-flow.xml`,
  `flows/**/*.xml`, spring XML, etc.; `exclude_globs` cover `bin/`, `build/`, `target/`,
  `.git/`, `legacylift-docs/index/**`.
- A **stale** index exists at
  `legacy/customer.ple.nng.app/legacylift-docs/index/code-search/` (index.sqlite ~185 MB, built
  Jul-2, **pre-enhancement, no knowledge.sqlite**). `index --reset` wipes and rebuilds it.
- `modernize-assess` skill lives at `.claude/skills/code-modernization/commands/modernize-assess.md`
  and is the **repo's enhanced copy** (upstream plugin disabled — see the
  `code-mod-agents-stock-not-enhanced` memory). Its Step 6 already emits `analysis/$1/domains.json`
  and renders `ARCHITECTURE.mmd` via `legacylift-search render-architecture --domains ...`.
- Bedrock auth: `AWS_BEARER_TOKEN_BEDROCK` in `.claude/settings.local.json` `env`
  (`bedrock-embedder-creds` memory). AWS-scoped; Claude stays on Enterprise license.
- chromadb must be pinned **1.5.9** (`chromadb-version-pin` memory). The `update`-merge and the
  `#57` vector-fill assumption are only verified for 1.5.9. A benign Rust-backend teardown panic
  on Windows process exit is expected noise (not a failure).

---

## 3. Path conventions (critical — do not skip)

The modernize skills use `legacy/$1` for input and `analysis/$1` for output, both resolved
relative to a working directory where `legacy/` and `analysis/` are siblings. That directory is:

    C:\Users\dnorton\captechdev\legacylift-ai\repos\nng-app-legacylift-analysis
    (bash: /c/Users/dnorton/captechdev/legacylift-ai/repos/nng-app-legacylift-analysis)

So run the modernize skills with that as the effective working dir, with:
- `$1 = customer.ple.nng.app`         → repo-root `legacy/customer.ple.nng.app`
- `$1 = customer.ple.nng.db.ETSPii`   → repo-root `legacy/customer.ple.nng.db.ETSPii`

Skills write to `analysis/<system>/`. **The skills' `analysis/$1/...` paths are hard-coded**
(e.g. the `render-architecture --domains analysis/$1/domains.json` shell-out, and the input to
`tag-domains`). So: **let the skills write to `analysis/<system>/` during the run, then
consolidate into `analysis-domains-enhanced/<system>/` in Stage F.** Do NOT edit the skills to
redirect output. If an `analysis/` dir does not exist it will be created; it is a scratch
staging dir — the deliverable is `analysis-domains-enhanced/`.

Shell note: primary shell is PowerShell; the Bash tool is also available. `legacylift-search`
commands run from `tools/legacylift_search`. **Prefer absolute paths in every command** to
avoid cwd confusion between the two working directories.

Absolute anchors used below:
- `TOOL   = C:\Users\dnorton\captechdev\legacylift-ai\tools\legacylift_search`
- `NNG    = C:\Users\dnorton\captechdev\legacylift-ai\repos\nng-app-legacylift-analysis`
- `APP    = %NNG%\legacy\customer.ple.nng.app`
- `DB     = %NNG%\legacy\customer.ple.nng.db.ETSPii`
- `OUT    = %NNG%\analysis-domains-enhanced`

---

## 4. Phase 0 — Preconditions (fail fast BEFORE the multi-hour jobs)

0.1 **chromadb pin.** From `TOOL`: `py -3.12 -c "import chromadb; print(chromadb.__version__)"`
    → must be `1.5.9`. If not, install the pin before continuing.

0.2 **Bedrock auth smoke test.** Confirm `AWS_BEARER_TOKEN_BEDROCK` is set, then embed a single
    file (e.g. index one tiny throwaway copy, or run any command that forces one Titan call) to
    fail fast on stale creds. Do NOT start a 97k-LOC index only to have auth fail an hour in.

0.3 **DB-project manifest.** `DB` has no manifest. Create one:

        cd %TOOL%
        py -3.12 -m legacylift_search.cli init-config --repo-root "%DB%"

    Then open `%DB%\semantic-search.manifest.json` and confirm:
    - `include_globs` cover `**/*.sql`, `**/*.ddl`, `**/*.dml`, `**/*.psql`, `**/*.tsql`;
    - the `embedding` block matches the APP manifest (provider `api`, Titan v2, us-east-2) —
      if `init-config` defaulted to a hash/other provider, **copy the APP manifest's `embedding`
      block over it** so both units embed identically.

0.4 **Preflight.** Run the `modernize-preflight` skill from `NNG` (checks scc / cloc / lizard /
    legacylift-search on PATH, source completeness). Save its report to `%OUT%\PREFLIGHT.md`.

---

## 5. Pipeline — run Stages A–F once per unit (APP first, then DB)

### Stage A — Index (long pole; exercises M1)

    cd %TOOL%
    py -3.12 -m legacylift_search.cli index --repo-root "<REPO>" --reset

- Wipes + rebuilds `<REPO>\legacylift-docs\index\code-search\` (index.sqlite + Chroma), and
  **creates the durable `<REPO>\legacylift-docs\knowledge\knowledge.sqlite`** (M1: construction
  migrates it). Uses Bedrock Titan from the manifest — no `--embedding-provider` override.
- **Hours-class job** at 97k LOC over the Bedrock API. **Run in the background and Monitor to
  completion** before Stage B — assess needs a `fresh` index for Layer-0 retrieval. The DB unit
  is a second, smaller cold index.
- On completion, sanity check: `validate --repo-root "<REPO>"` should report the index `fresh`
  and a `domains: missing` line (no tags yet — expected).

### Stage B — Assess (exercises M3 + M8)

Run the `modernize-assess` skill for the unit (working dir `NNG`, `$1 = <system>`). It:
- spawns legacy-analyst / security-auditor subagents (uses the fresh index for retrieval);
- writes `analysis/<system>/ASSESSMENT.md` (secrets quarantined to `~/.modernize/<system>/`
  per the skill's Step 6);
- **emits `analysis/<system>/domains.json`** (schema_version 1, domains[] with `path_globs`,
  edges[]) — **M3**;
- shells out to render `analysis/<system>/ARCHITECTURE.mmd` from that JSON — **M8** (assess-time
  `--domains` source path, no `--repo-root`).

Capture the domain list assess produced; the baseline `analysis-original` table had ~10 domains
(LES, POI, Surveys, EDI & Type Maint, Reference/Geo, Notifications, Security, External, Web UI,
REST API) — compare.

### Stage C — Tag domains (exercises M4)

    cd %TOOL%
    py -3.12 -m legacylift_search.cli tag-domains --repo-root "<REPO>" ^
        --domains "%NNG%\analysis\<system>\domains.json"

- Ingests `domains.json` into `knowledge.sqlite` (`domains` + `domain_edges`), resolves each
  domain's globs against the discovered file set (`source='glob'`), sends unmatched files to
  `unassigned`, and stamps each chunk's Chroma `domain` metadata **with no re-embedding**.
- **Record the run notices:** manual-override count, any dropped-domain reap notice, and any
  ambiguous-glob-match warnings (a file matching two domains) — these are data-quality signals.

### Stage D — Map

Run the `modernize-map` skill (`$1 = <system>`) → call-graph / critical-path / data-lineage /
topology artifacts into `analysis/<system>/`.

**Domain-set consistency assertion (2026-07-23):** `modernize-map` now pins its topology
`domain` containers to the canonical `domains.json` (one `dom:<domain_id>` per entry; unmatched
files → `dom:unassigned`). Confirm the topology's domain containers match the canonical set:
the `dom:*` container ids in `analysis/<system>/topology.json` must equal the `domain_id`s in
`analysis/<system>/domains.json` (plus the synthesized `dom:unassigned`) — same set, no invented
domains. A mismatch means map re-derived domains instead of reading `domains.json` (a regression
in the pin) → record as a finding.

### Stage E — Extract rules — **DEFERRED (2026-07-23), do not run this run**

**Rationale:** `modernize-extract-rules` does **not** consume any domain-enhancement surface.
It reads the index (`validate` index-freshness axis, semantic search *without* `--domain`, and
`coverage` against `index.sqlite`) but touches none of M1–M8: no `knowledge.sqlite` domains, no
`tag-domains`/`domains`/`render-architecture`, no `--domain` filter, and it ignores the
`validate` `domains:` line. Consequently **all domain milestones (M1–M8) and the #57 probe are
fully determinable by the end of Stage D (map)** — in fact by the end of Stage C (tag-domains);
nothing in the §6 battery reads extract-rules output. Skipping Stage E therefore forfeits **no
milestone result** — only the `BUSINESS_RULES.md` / `DATA_OBJECTS.md` deliverables and the
non-milestone `coverage` exercise. Extract-rules changes are pending; running it now would be
thrown-away work to regenerate after those changes land. **Run preflight → assess → tag-domains
→ map, then stop.**

When the pending extract-rules changes land, run this stage then (and regenerate the
deliverables): the `modernize-extract-rules` Workflow with `args {system: "<system>",
maxRounds: 4}` returns rule cards; the session writes `analysis/<system>/BUSINESS_RULES.md` +
`DATA_OBJECTS.md`. **Stop at the 4-round cap and post a status update** (rounds run, rules
found, P0 count / crossover) — do NOT loop beyond 4.

Harness quirk (`workflow-launch-harness-quirks` memory): workflow scripts here can choke on
non-ASCII and receive `args` as a JSON string. If the named workflow errors on launch, fall
back to the ASCII-copy + args-shim from the scratchpad.

### Stage F — Consolidate

Copy `%NNG%\analysis\<system>\` → `%OUT%\<system>\`. (PowerShell:
`Copy-Item -Recurse -Force "$env:NNG\analysis\<system>\*" "$env:OUT\<system>\"`.)
With Stage E deferred, this consolidates the assess + tag + map artifacts (no
`BUSINESS_RULES.md` / `DATA_OBJECTS.md` this run).

**Then repeat A–D + F for the second unit** (Stage E deferred for both units).

---

## 6. Domain-enhancements verification battery (the core "test")

After BOTH units are tagged, run this per unit and record every command + verbatim output into
`%OUT%\DOMAIN-ENHANCEMENTS-TEST-REPORT.md`, one section per milestone (mark each pass / fail /
finding). All `legacylift-search` commands run from `%TOOL%` with `--repo-root "<REPO>"`.

- **M1 durability.** Write a sentinel row into `knowledge.sqlite` (throwaway table), run
  `index --reset`, confirm the sentinel **survives** while `index.sqlite` was recreated.
  Command form (from the source plan's Concrete Steps):
  `py -3.12 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('CREATE TABLE IF NOT EXISTS _sentinel(id INTEGER)'); c.execute('INSERT INTO _sentinel VALUES (1)'); c.commit()" "<REPO>\legacylift-docs\knowledge\knowledge.sqlite"`
  then re-run `index --reset` and `SELECT count(*) FROM _sentinel` → expect `(1,)`.

- **M2 catalog + stats.** `domains --repo-root "<REPO>"` — expect the assess domains each with
  **real, non-zero** per-domain file & chunk counts plus a synthesized `unassigned` trailer.
  `stats --repo-root "<REPO>"` — expect the `N domains · M files tagged · K unassigned` summary.
  Confirm "files tagged" counts classified files only (not unassigned).

- **M6 `search --domain`.** Run several real queries scoped and unscoped; confirm scoped results
  are a **strict in-domain subset** of unscoped and a result's `relative_path` prefix matches
  the domain. Examples (APP):
  - `search "legal entity address validation" --repo-root "<REPO>" --domain "Legal Entity (LES)"`
  - `search "pipeline point survey record" --repo-root "<REPO>" --domain "Point / Poipoint (POI)"`
  - `search "templated notification email" --repo-root "<REPO>" --domain "Notifications & Email"`
  On the **DB** unit, run a lexical-heavy query — a distinctive SQL identifier that appears in
  one in-domain file but is not semantically close to the query embedding — to exercise the
  `#54` in-domain dense re-rank (this is where real Bedrock embeddings matter vs the fixture).
  Also verify the error paths: `--domain "Nonexistent"` lists available domains (not empty
  results), and `--domain` on a never-tagged repo errors "run tag-domains first".

- **M5 7-Auto + manual-wins.**
  (a) Add a new source file under an existing domain's glob (e.g. a `.java` under a matched
      package), run **incremental** `index` (no `--reset`), confirm it gets a `glob`
      `file_domains` row and its chunk carries Chroma `domain` — with **no** `tag-domains` call.
  (b) Hand-edit one file's `file_domains` row to `source='manual'` with a **different** domain,
      rewrite that file's body (so its chunk truly re-embeds) and reindex; confirm (i) the row
      still reads `manual`/that domain (7-Auto did not overwrite), and (ii) that chunk's Chroma
      `domain` flipped to the manual value.
  (c) `index --reset`; confirm knowledge DB + manual rows survive and existing `glob` rows are
      mirrored into Chroma (not recomputed).

- **M7 `validate` freshness.** Right after tag: expect
  `domains: fresh · coverage <100% · N unassigned` (the unmatched dirs are *accepted*
  `unassigned` gaps, NOT staleness). Then add a file matching **no** glob and reindex → expect
  `domains: stale · … untagged (need assess)`. Add a file matching a glob **without**
  reindexing → `stale · … untagged (glob-matchable)`; reindex → back to `fresh`.

- **M8 `render-architecture`.** `render-architecture --repo-root "<REPO>" --output -` (SQLite
  source, post-tag). Confirm it is consistent with the assess-time `--domains` render from
  Stage B, and compare the derived `ARCHITECTURE.mmd` against
  `analysis-original\<system>\ARCHITECTURE.mmd` (the old hand-authored one) — the derived
  diagram should track the same domain topology, now generated deterministically.

- **`#57` at-scale vector-fill probe (NEW FINDING TO CAPTURE).** This is the first real
  at-scale `--domain` run on chromadb 1.5.9. The source plan flagged as *unverified* whether
  Chroma's metadata `where` fills `n_results` from the in-domain set on a large collection
  (HNSW + filter can under-fill). Probe a filtered `collection.query(..., where={"domain": ...},
  n_results=40)` on the large NNG collection and record whether it returns a full pool. If it
  under-fills, that is a real finding → note that the vector arm needs the same pool-scaling
  lever the lexical arm got under `--domain`. Update the `domain-search-vector-recall-57` memory
  with the at-scale result.

---

## 7. Deliverables layout (`analysis-domains-enhanced/`)

    customer.ple.nng.app/
        ASSESSMENT.md              (Stage B)
        domains.json               (Stage B, M3)
        ARCHITECTURE.mmd           (Stage B, M8 — render-architecture derived)
        call-graph.mmd / critical-path.mmd / data-lineage.mmd / topology.json  (Stage D)
        BUSINESS_RULES.md / DATA_OBJECTS.md   (Stage E — DEFERRED this run; not produced)
    customer.ple.nng.db.ETSPii/
        (same set, as applicable to a SQL-only unit)
    PREFLIGHT.md                   (Phase 0.4)
    DOMAIN-ENHANCEMENTS-TEST-REPORT.md   (§6 — M1–M8 observed behavior + #57 probe)

---

## 8. Risks & operational notes

- **Runtime.** Two cold Bedrock indexes dominate wall-clock (hours). Run index jobs in the
  background with Monitor; assess/map/extract are long in-session subagent runs. Fully sequence
  the APP unit, then the DB unit. Do not start assess before its index is `fresh`.
- **Benign Chroma teardown panic** on Windows process exit (1.5.9 Rust backend) — appears after
  results return; ignore it (documented in the source plan's Surprises & Discoveries).
- **.gitignore depth.** `knowledge.sqlite` / `index/` here sit at
  `repos/nng-app-legacylift-analysis/legacy/<unit>/legacylift-docs/…` — one directory level
  **deeper** than the M1 `.gitignore` rules (`repos/*/…` and `repos/*/*/…`). These are runtime
  artifacts, not deliverables. **Verify they are ignored (or leave uncommitted) before any
  commit.** Only `analysis-domains-enhanced/` is meant to be committed/shared.
- **DATA_OBJECTS/BUSINESS_RULES stay file-based** — generating them from SQLite via
  `symbol_facts` is deferred future work; extract-rules writes the markdown as today.
- **DB-unit domains.** assess's domain globs are authored for the Java app; on the SQL unit,
  expect a higher `unassigned` share and treat that as a real coverage finding, not a bug
  (`validate` will show it on the coverage axis, still `fresh`).

---

## 9. Done-when

1. `%OUT%\<unit>\` exists for **both** units with ASSESSMENT.md, domains.json, a
   render-architecture-derived ARCHITECTURE.mmd, and map diagrams. (BUSINESS_RULES +
   DATA_OBJECTS from the 4-round extract are **deferred** with Stage E — see Stage E rationale;
   they are not required for this run.)
2. `knowledge.sqlite` exists per unit; `domains` lists the assess domains with non-zero real
   file/chunk counts; `validate` reports a `domains:` line; `search --domain` returns strict
   in-domain subsets; M5 auto-tag + manual-wins checks pass; the M1 sentinel survives `--reset`.
3. `%OUT%\DOMAIN-ENHANCEMENTS-TEST-REPORT.md` records each of M1–M8 as pass / fail / finding on
   the real repo, including the `#57` vector-fill probe result. (This is fully satisfiable
   without Stage E — no milestone depends on extract-rules output.)
4. ~~Extract stopped at the 4-round cap with a posted status update.~~ **N/A — Stage E deferred
   this run.** Applies only when the pending extract-rules changes land and Stage E is run.

---

## 10. Execution checklist — COMPLETE (executed 2026-07-23; ticks reconciled 2026-07-30)

- [x] 0.1 chromadb 1.5.9 confirmed
- [x] 0.2 Bedrock auth smoke test passed
- [x] 0.3 DB-project manifest created + embedding block verified
- [x] 0.4 preflight run → PREFLIGHT.md
- [x] APP: A index (--reset, Bedrock, background+monitor) → knowledge.sqlite created
- [x] APP: B modernize-assess → ASSESSMENT.md + domains.json + ARCHITECTURE.mmd
- [x] APP: C tag-domains → notices captured (19 ambiguous-glob warnings)
- [x] APP: D modernize-map (+ assert topology `dom:*` ids == domains.json `domain_id`s + `dom:unassigned`)
- [~] APP: E extract-rules — **DEFERRED, still not run.** No milestone depends on it; gated on the
      pending extract-rules changes. This is the only item in this plan never executed.
- [x] APP: F consolidate → analysis-domains-enhanced/customer.ple.nng.app/
- [x] DB: A index (--reset, Bedrock) — **re-run 2026-07-30** after the SQL extractor fix
- [x] DB: B modernize-assess
- [x] DB: C tag-domains (71 ambiguous-glob warnings)
- [x] DB: D modernize-map (+ topology `dom:*` assertion) — **re-run 2026-07-30**, now index-seeded
      instead of grep-built; output in `analysis/customer.ple.nng.db.ETSPii/`
- [~] DB: E extract-rules — **DEFERRED** (see APP: E)
- [x] DB: F consolidate → analysis-domains-enhanced/customer.ple.nng.db.ETSPii/ — *note: holds the
      2026-07-23 snapshot; not re-consolidated after the 2026-07-30 map re-run*
- [x] Battery: M1 sentinel durability
- [x] Battery: M2 domains + stats
- [x] Battery: M6 search --domain (scoped subset + error paths + DB lexical re-rank)
- [x] Battery: M5 7-Auto + manual-wins + reset-survival
- [x] Battery: M7 validate freshness (fresh → stale → fresh)
- [x] Battery: M8 render-architecture (SQLite vs domains.json vs baseline)
- [x] Battery: #57 at-scale vector-fill probe → finding + memory update (`domain-search-vector-recall-57`)
- [x] TEST-REPORT.md written; done-when §9 satisfied (items 1–3; item 4 N/A with Stage E deferred)
