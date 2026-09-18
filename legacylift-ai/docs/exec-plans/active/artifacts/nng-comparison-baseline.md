# NNG PLE app — grep-baseline vs. enhanced code-mod comparison (setup + baseline facts)

_Started 2026-07-01. Target: `customer.ple.nng.app` — Spring Boot 2.7.5 / Spring WebFlow / Hibernate monolith, ~97k Java LOC, 6 Gradle modules, EAR-packaged for WebSphere 8.5. Repo kept local under `repos/nng-app-legacylift-analysis/` (gitignored; client code + original outputs never committed)._

## What this compares

The `analysis/customer.ple.nng.app/` folder holds the **original code-modernization plugin** outputs (grep discovery). This exercise runs the **enhanced** plugin (legacylift-search semantic + graph + chunk-coverage as Layer-0) against the **same source** under `legacy/customer.ple.nng.app/`, holding the verification discipline (citation referee, P0 panel) constant, to measure the discovery delta on rules count, coverage, and quality.

## Baseline (original code-mod, grep discovery) — the target to beat

From `BUSINESS_RULES.md` + `plans.md`:

- **815 distinct rules** after dedup by `file:line`+name — **55 P0 · 614 P1 · 146 P2**.
- By category: **Validation 441 · Lifecycle 215 · Policy 101 · Calculation 58**.
- Quality controls: every rule citation-refereed; P0s passed a two-judge panel; **38 rejected**; 173 carry an SME question; 20 flag a suspected defect.
- **Took 3 merged runs** to get there — and the baseline says so explicitly:

  | Run | Confirmed | New | Focus |
  |---|---|---|---|
  | full-system | 229 | 229 | ple-services |
  | ple-persistence | 197 | 197 | DAO/criteria/interceptor |
  | ple-web | 389 | 389 | WebFlow screen/action |

  > _"the original single run captured only ~28% of the system's rules"_ (229 of 815). The two extra runs were **hand-scoped** deep-dives into modules the first run under-covered — precisely the gap the enhancement's chunk-level coverage targets automatically.
- Baseline discovery footprint: **285 of 995 Java files** cited; **616 distinct `path:line-line` citations** extracted from `BUSINESS_RULES.md`.

Topology baseline (`/modernize-map`): 302 Spring beans, 45 tables, **521 edges** (467 call via `@Autowired` DI + 54 data via DAO→entity(`.hbm.xml`)→table); 63 entry points; 6 dead-ends after dispatch suppression.

## Enhanced index — built 2026-07-01 (Titan/Bedrock, same embedder as ctcm)

`legacylift-search index --repo-root repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app` (exit 0). Manifest placed at the **app root** so indexed paths match the baseline's citation shape (`ple-services/...`, `ple-web/...`) exactly.

| Metric | Value |
|---|---|
| files indexed | 1,056 |
| chunks | 15,055 |
| symbols | 16,271 |
| refs | 65,715 |
| graph edges | **64,468** |
| languages | java, **xml**, sql, javascript |
| embedder | api:bedrock:amazon.titan-embed-text-v2:0 (dim 1024) |
| freshness | fresh (validate OK; Chroma vector path healthy) |

_Rebuilt 2026-07-02 with the new framework-aware XML extractor (Hibernate/WebFlow/Spring) AND vendored-JS exclusion. See `xml-hibernate-extractor.md` for the tool change. The earlier build (21,381 chunks) is superseded: it lacked XML and included ~6,772 vendored-JS junk chunks (jQuery/prototype/dataTables) that both polluted the coverage denominator and caused a chunker hang — now excluded._

### Data-lineage edges (the new capability this rebuild adds)

Chunk composition: java 14,381 · xml 215 · sql 228 · javascript 231. Graph edge kinds:

| edge_kind | count | meaning |
|---|---|---|
| calls | 55,225 | Java method/DI call graph |
| references | 6,508 | generic refs |
| uses_column | 1,332 | hbm property → DB column |
| **uses_table** | **740** | hbm/entity → **DB table** (data lineage) |
| associates | 181 | entity → entity (many-to-one etc.) |
| instantiates | 159 | Spring bean → Java class |
| **maps_to** | **147** | hbm mapping → **Java entity class** |
| transitions_to | 132 | WebFlow state transitions |
| invokes_subflow | 44 | WebFlow subflow calls |

**The DAO→entity→table bridge works end-to-end:** all **147 `maps_to` edges resolved** to a real Java entity class symbol (0 unresolved) — e.g. `ContactSearchAndReplaceLite.hbm.xml → ContactSearchAndReplaceLite`. `uses_table` edges name the physical tables (`LESContact`, `ETSCompany`, `FIPSCity`); most sit at confidence 0.3 (preserved-unresolved) because the DDL lives in the **sibling** `customer.ple.nng.db.ETSPii` repo, which is not indexed here — the correct representation (names the table even without its DDL). This is a strict superset of the baseline's 54 hand-built `.hbm.xml` data edges (740 table + 147 entity + 1,332 column + 181 association).

## Free data point — coverage of the 815-rule baseline (clean index)

Ran the new `coverage` command with the baseline's own 616 citations as `--claimed`, against the clean XML-inclusive index:

```
coverage: 1143/15055 chunks claimed (7.6%); 13912 uncovered chunks
```

- vs **all** chunks: 1,143 / 15,055 = **7.6%** (was diluted to 5.3% by the ~6,772 junk JS chunks in the first build)
- Reading unchanged: even the exhaustive 3-run, 815-rule baseline claims only ~1 in 13 chunks; the highest-value uncovered chunks are dominated by `ple-services-test/*Test.java` — the rule-improbable code the plan's "richer chunk classification" Future Work item targets. A truer domain-logic coverage number needs chunk classification to drop test/generated from the denominator.

## Discovery smoke tests (all query paths healthy)

- **Semantic search** for "overlapping date range records trimmed or split to stay contiguous" → top hits `DateRangeService.java:25-428`, `DateRangeSplitter.java:19-497` — exactly the files the baseline's #1 P0 rule (date-split adjacency) cites. Paths match baseline citation shape.
- **symbols --name DateRangeSplitter** → returns the class symbol (table renders; note `symbols`/`callers`/`callees` have no `--json` flag — human table only).

## Next decision (paused here per operator)

Index is ready. Operator chose "build the index first, then decide extraction scope with real numbers." When extraction runs, it will **drive the `modernize-extract-rules` workflow directly** with `repoRoot` wired, capturing real per-round coverage logs. Candidate scopes: single full-system run (head-to-head vs the baseline's 229/28% first run) or full 3-run reproduction (vs the merged 815).
