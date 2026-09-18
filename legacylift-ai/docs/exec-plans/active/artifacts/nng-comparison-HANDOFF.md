# HANDOFF — NNG PLE grep-baseline vs. enhanced code-mod comparison

_Written 2026-07-02 for a fresh agent picking up cold. **The open decision is at the very bottom: "single full-system run vs. full 3-run reproduction."** Read this top-to-bottom first; everything you need is here or linked._

---

## ✅ RESOLVED 2026-07-06 — Option A executed, see `nng-comparison-RESULTS.md`

The decision below was answered: **Option A (single enhanced self-steering run)**. Result: **470 confirmed rules (61 P0, 0 rejected)** at a 12-round cap (never dried), vs. the baseline's first full-system run of 229 (2×+) and 58% of the full 3-run 815 in one run with no hand-scoping — plus a **P0 crossover (61 > baseline's 55 across all 3 runs)**. Full analysis, trajectory, and caveats: **`docs/exec-plans/active/artifacts/nng-comparison-RESULTS.md`**. The rest of this handoff is retained for historical context.

---

## 0. The one decision waiting for you

The NNG PLE app's `legacylift-search` index is **built, clean, validated, and ready**. The next action is to run the **enhanced** `/modernize-extract-rules` against it and compare the result to the **original** code-mod run's `BUSINESS_RULES.md`. The operator must choose the scope; do **not** start extraction until they answer:

- **Option A — Single full-system run.** One enhanced `modernize-extract-rules` full-system run. Cleanest head-to-head vs. the baseline's *first* full-system run (229 rules / ~28% capture). Best isolates "does semantic+graph+chunk-coverage find more per run." Hours, moderate tokens.
- **Option B — Full 3-run reproduction.** Reproduce all three runs (full-system + ple-persistence + ple-web), merge, diff against the 815-rule baseline. Most complete; multi-hour, high token cost.

Method (already decided by operator): **drive the `code-modernization:modernize-extract-rules` workflow directly** in-session with `repoRoot` wired, capturing real per-round coverage logs — not a simulation. See §5 for exactly how.

---

## 1. What this comparison is

Two systems ingest the **same** legacy codebase and mine business rules:
- **Baseline** = the *original* Anthropic code-modernization plugin (grep discovery). Its outputs already exist in this repo (§3).
- **Enhanced** = the same plugin after the `code-modernization-layer0-retrieval` ExecPlan wired `legacylift-search` (semantic search + confidence-scored call graph + chunk-level coverage) underneath its discovery agents as "Layer 0."

Goal: measure the discovery delta — **rules count, coverage, quality** — holding the verification discipline (citation referee, P0 panel) constant. Governing ExecPlan: `docs/exec-plans/completed/code-modernization-layer0-retrieval.md` (Milestone 6 = this validation; the plan is now fully complete and archived).

The target system: **`customer.ple.nng.app` (PLE)** — Spring Boot 2.7.5 / Spring WebFlow / Hibernate monolith, ~97k Java LOC, 6 Gradle modules, EAR-packaged for WebSphere 8.5.

---

## 2. Repo locations (all under `repos/nng-app-legacylift-analysis/`, GITIGNORED — client code + original outputs, never commit)

- `legacy/customer.ple.nng.app/` — the **source** (995 java files). This is the `--repo-root` for every `legacylift-search` command AND the on-disk path the extraction workflow's `repoRoot` arg must point at.
- `legacy/customer.ple.nng.db.ETSPii/` — sibling DB repo (DDL). **Not indexed** (that's why hbm `uses_table` edges are mostly preserved-unresolved — see §4).
- `analysis/customer.ple.nng.app/` — the **original code-mod outputs** = the baseline to beat.

The gitignore entry `repos/nng-app-legacylift-analysis/` is committed-pending in `.gitignore` (see §7).

---

## 3. The baseline to beat (original code-mod, grep discovery)

From `analysis/customer.ple.nng.app/BUSINESS_RULES.md` + `plans.md`:

- **815 distinct rules** (dedup by `file:line`+name) — **55 P0 · 614 P1 · 146 P2**.
- By category: **Validation 441 · Lifecycle 215 · Policy 101 · Calculation 58**.
- Quality gates: every rule citation-refereed; P0s passed a two-judge panel; **38 rejected**; 173 carry an SME question; 20 flag a suspected defect.
- **Took 3 merged runs.** The baseline *explicitly says* the first single run captured only **~28%** (229 of 815); the other two were **hand-scoped** deep-dives into under-covered modules:

  | Run | Confirmed | New | Focus |
  |---|---|---|---|
  | full-system | 229 | 229 | ple-services |
  | ple-persistence | 197 | 197 | DAO/criteria/interceptor |
  | ple-web | 389 | 389 | WebFlow screen/action |

- Discovery footprint: 285 of 995 java files cited; **616 distinct `path:line-line` citations**.
- Topology baseline (`/modernize-map`): 302 beans, 45 tables, **521 edges** (467 call + 54 hbm-derived data). 63 entry points.

**Why the enhancement should help (the thesis to test):** the 28%-per-run tail is exactly what chunk-level coverage + semantic/graph discovery attack. Hypotheses: (a) more rules per single run than 229; (b) coverage self-steers into the tail that needed 3 hand-scoped runs; (c) semantic discovery surfaces rules in files the 285-file grep footprint missed; (d) rules survive the *same* referee/P0 gates (quality parity).

---

## 4. The enhanced index — BUILT & READY (2026-07-02)

Command that built it (re-run verbatim to rebuild):
```
py -3.12 -m legacylift_search.cli index --repo-root repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app --reset
```
Verify it's usable:
```
py -3.12 -m legacylift_search.cli validate --repo-root repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app
py -3.12 -m legacylift_search.cli stats    --repo-root repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app
```

Current state — **fresh, valid, Chroma vector path healthy**:

| Metric | Value |
|---|---|
| files | 1,229 (java 995 · xml 183 · sql 50 · js 1) |
| chunks | 15,055 (java 14,381 · xml 215 · sql 228 · js 231) |
| symbols | 16,271 |
| graph edges | 64,468 |
| embedder | api:bedrock:amazon.titan-embed-text-v2:0 (dim 1024, region us-east-2) |

Edge kinds: calls 55,225 · references 6,508 · uses_column 1,332 · **uses_table 740** · associates 181 · instantiates 159 · **maps_to 147** · transitions_to 132 · invokes_subflow 44.

**Hibernate data-lineage works end-to-end:** all **147 `maps_to` edges resolved** to real Java entity classes (0 unresolved). `uses_table` names physical tables (`LESContact`, `ETSCompany`…) at conf 0.3 (preserved-unresolved because DDL lives in the un-indexed sibling DB repo — correct behavior). This is a strict superset of the baseline's 54 hand-built hbm data edges.

**Free data point (no extraction):** baseline-coverage = **7.6%** (`coverage --claimed` with the baseline's 616 citations): even the 815-rule/3-run baseline claims only ~1 in 13 chunks; uncovered set dominated by `*Test.java`.

Details: `docs/exec-plans/active/artifacts/nng-comparison-baseline.md`.

---

## 5. HOW to run the extraction (when the operator answers)

The workflow needs the on-disk repo root passed as `repoRoot` so per-round chunk coverage runs. Invoke the workflow (it's the `code-modernization:modernize-extract-rules` skill/Workflow):

- **Option A (single run):** run once with `args = { system: "customer.ple.nng.app", repoRoot: "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app" }` (add `modulePattern` only if scoping). The workflow returns structured rule cards; the calling session writes `BUSINESS_RULES.md`/`DATA_OBJECTS.md`. Watch the per-round `Round N coverage: …` log — the metric should climb across rounds.
- **Option B (3-run):** run full-system, then a `ple-persistence`-scoped run, then a `ple-web`-scoped run (use `modulePattern`), then merge (baseline used `merge_rules.py`, present in the analysis folder as a reference).

Preflight is already satisfied (index fresh). The discovery agents will prefer `legacylift-search` automatically per the Layer-0 wiring. **Do not** modify the referee or P0 panel — quality parity is the point.

Then compare to baseline: counts by priority/category, per-file overlap vs. the 285-file baseline footprint, rules found in files the baseline never cited (semantic wins), and final chunk-coverage % vs. the baseline's 7.6%.

---

## 6. Environment gotchas (learned the hard way — save yourself hours)

- **Invocation form:** use `py -3.12 -m legacylift_search.cli …`. The on-PATH `legacylift-search` console script resolves to a Python 3.14 interpreter here. A working venv also exists: `tools/legacylift_search/.venv/Scripts/legacylift-search.exe`.
- **`chromadb` MUST be `==1.5.9`** globally (it is). An older transitively-installed `1.1.1` (via `crewai`) panics on the store. See memory `[[chromadb-version-pin]]`.
- **`--reset` is destructive:** it wipes the index BEFORE rebuilding. If a rebuild stalls, you're left worse off. Prefer building without `--reset` unless you truly need a clean slate; if a build hangs, kill it fully before retrying (see next).
- **Windows SQLite lock (`WinError 32`):** a stalled/killed build leaves orphaned worker processes holding `index.sqlite`. Symptoms: retry fails with WinError 32. Fix: `taskkill //IM python.exe //F` (or kill the specific `py.exe`→python tree), then `rm -f <indexdir>/index.sqlite-wal <indexdir>/index.sqlite-shm`.
- **Python writes `/tmp/…` to `C:\tmp\…`** under this Git Bash — read progress files at `/c/tmp/...`.
- **Bedrock creds** are live in-session (`AWS_BEARER_TOKEN_BEDROCK`, `AWS_PROFILE=ailab`, `AWS_REGION`). Manifest pins region `us-east-2` for Titan; verified working.
- **Long builds auto-background** and notify on completion. Don't `sleep` >110s in one Bash call (2-min tool cap); poll instead.

---

## 7. TOOL CHANGES made this session — NOT YET COMMITTED (⚠️ action needed before shutdown)

To include Hibernate `.hbm.xml` (+ WebFlow/Spring) in the index, a real framework-aware XML extractor was added to the shared `legacylift-search` tool. Full design: `docs/exec-plans/active/artifacts/xml-hibernate-extractor.md`. Summary of the diff (`git status` shows all of it uncommitted on branch `feature/semantic-code-search-graph-index`):

- **NEW `tools/legacylift_search/src/legacylift_search/xml_extractor.py`** — expat-based; Hibernate (class→table `uses_table`, hbm→entity `maps_to`, property→column, associations), WebFlow (states, `evaluate`→Java calls, transitions, subflows), Spring beans (bean→class). Unknown XML → 1 searchable symbol. Malformed → parse error, no hang.
- **`languages.py`** — registered `xml` language (extension `.xml`, no tree-sitter). Without this, discovery skips all `.xml`.
- **`extractors.py`** — `SymbolExtractor.extract()` dispatches `language=="xml"` to `xml_extractor` before the tree-sitter/profile path.
- **`graph.py`** — XML ref-kind → edge-kind map (`uses_table`/`maps_to`/`associates`/`uses_column`/`instantiates`/`invokes_subflow`/`transitions_to`).
- **`chunking.py`** — **BUG FIX:** XML never goes to Chonkie (its `language="auto"` infinite-loops on a comment-wrapped `.hbm.xml` — the real file `ple-persistence/JavaSource/config/hbm/external/DunsSetup.hbm.xml` is a whole mapping disabled inside one `<!-- -->`). Symbol-less XML → deterministic line-based chunking. This was a latent pre-existing bug any repo with a disabled XML mapping would hit.
- **`config.py`** — default `include_globs` gained targeted XML patterns (`**/*.hbm.xml`, `**/flows/**/*.xml`, `**/config/**/*.xml`, etc. — NOT blanket `**/*.xml`); default `exclude_globs` gained `.settings/`, `build.xml`, `pom.xml`, AND vendored-JS excludes (`**/content/javascript/lib/**`, `**/jquery*.js`, `**/prototype.js`, `**/vendor/**`). → **"automatic in the future": any repo indexed without a custom manifest now picks up Hibernate/WebFlow/Spring XML and skips vendored JS.**
- **NEW `tools/legacylift_search/tests/test_xml_extractor.py`** — 13 tests incl. the DunsSetup chunker-hang regression.
- **`.gitignore`** — added `repos/nng-app-legacylift-analysis/`.
- **This repo's manifest** (`legacy/customer.ple.nng.app/semantic-search.manifest.json`, gitignored) mirrors the new globs. Note: `extract_workers:1` was added then REVERTED (it was only a serial-mode diagnostic; parallel is fine now the chunker bug is fixed).

**Test status: full suite 184 passed, exit 0.** `node --check` n/a (no JS workflow edited this session).

**⚠️ Recommendation:** commit the tool changes + the 3 handoff/artifact docs before shutdown so nothing is lost (the index artifact itself is gitignored and rebuildable via §4). Suggested: stage everything except the gitignored repo, commit on `feature/semantic-code-search-graph-index`, push. The operator's prior pattern was "commit, push, no PR."

---

## 8. Prior context (already committed, for orientation)

- The Layer-0 retrieval ExecPlan is complete through Milestone 6; commit `992cbf8a` recorded its own validation (against `repos/ctcm/ctcm-api`). This NNG exercise is an *additional*, richer validation of that same work on a real Java/Hibernate estate.
- Related memories: `[[chromadb-version-pin]]`, `[[qwen-embed-cpu-throughput]]`.
