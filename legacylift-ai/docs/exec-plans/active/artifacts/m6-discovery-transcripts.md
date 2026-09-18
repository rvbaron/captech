# Milestone 6 — End-to-end validation transcripts (repos/ctcm/ctcm-api)

_Captured 2026-07-01. Index: fresh, 58,677 chunks / 58,614 symbols / 141,219 graph edges, embedding api:bedrock:amazon.titan-embed-text-v2:0 (dim 1024). chromadb==1.5.9._

## Preflight — validate (Chroma vector path healthy on this host)
```
C:\Users\dnorton\captechdev\legacylift-ai\repos\ctcm\ctcm-api\legacylift-docs\i
ndex\code-search
OK sqlite: 58677 chunks, 58614 symbols, 141219 graph edges
OK chroma collection: code_chunks
OK embedding: api:bedrock:amazon.titan-embed-text-v2:0 dimension=1024
OK lexical search
freshness: fresh
Index is valid.
```

## Discovery comparison — three tasks (req-extraction §7)

### Task 1 — "where is provider eligibility validated?" (semantic vs. keyword grep)

**Index (semantic search).** Top hits (ranked by fused semantic+lexical score):
```
1. score=0.0164 
src/CTCM.API/CTCM.API.EntityService/Manager/HealthCareProviderManager.cs:21-481
2. score=0.0161 
src/CTCM.API/CTCM.API.EntityService/Manager/HealthCareProviderManager.cs:238-35
3. score=0.0159 src/CTCM.API/CTCM.API.EdiService/Manager/PocManager.cs:334-496 
4. score=0.0156 
src/CTCM.API/CTCM.API.EntityService/Manager/HealthCareProviderManager.cs:361-37
5. score=0.0154 
```
**Grep baseline** for the keyword `eligib` (`--include=*.cs`):
```
files matching 'eligib': 5
src/CTCM.API/CTCM.API.DocumentService/Dto/DocGen/RForm/RehabConsultationReportDocGenDto.cs
src/CTCM.API/CTCM.API.EdiService/BackgroundJobs/JurisdictionEntryBatchExportJob.cs
src/CTCM.API/CTCM.API.FilingService/Manager/RehabConsultationReport/RehabConsultationReportFactory.cs
src/CTCM.API/CTCM.API.UserService.Tests/Model/TeamModelFactoryTests.cs
src/CTCM.API/CTCM.API.WorkflowService/Manager/Notifications/NotificationManager.cs
```
**Delta.** The #1 semantic hit `HealthCareProviderManager.cs` contains **zero** `eligib` tokens (`grep -c -i eligib` = 0), so a keyword grep structurally never surfaces it. Semantic search found the provider-eligibility logic by meaning.

### Task 2 — "what calls `SpecialClaimManager.CreateReserveTask`?" (call graph vs. grep)

**Index (graph).** `symbols --name CreateReserveTask` → symbol id, then `callers`:
```
callers of CreateReserveTask:
| d               | edge_kind | confidence | path:line       | evidence       |
| csharp:src/CTCM | calls     | 0.85       | src/CTCM.API/CT | await          |
| imManager.cs:Sp |           |            | er.cs:881       | threshold);    |
```
The edge is resolved to the calling method with confidence 0.85, the exact call-site line (881), and the evidence snippet `await CreateReserveTask(reserveModel, newTotal, threshold);`.

**Grep baseline** for `CreateReserveTask`:
```
src/CTCM.API/CTCM.API.ClaimService/Manager/SpecialClaimManager.cs:881:            await CreateReserveTask(reserveModel, newTotal, threshold);
src/CTCM.API/CTCM.API.ClaimService/Manager/SpecialClaimManager.cs:1375:    private async Task CreateReserveTask(SpecialClaimReserve reserve, decimal newReserveTotal,
```
**Delta — preserved unresolved / dynamic-dispatch edges.** A grep call graph either drops dynamic-dispatch calls or false-positives on name collisions. The index keeps them as low-confidence edges. `callees` of the caller `CreateReserveAdjustmentAsync` shows both resolved and preserved-unresolved edges:
```
resolved static-call edges (confidence 0.85): 13
preserved unresolved edges (confidence 0.30, e.g. dynamic dispatch): 9
example unresolved edge (kept, not dropped):
| Identity       | (unresolved)    | references | 0.30       | src/CTCM.API/C |
| _specialClaimR | (unresolved)    | calls      | 0.30       | src/CTCM.API/C |
| _specialClaimR | (unresolved)    | calls      | 0.30       | src/CTCM.API/C |
```

### Task 3 — "find the appeal-case repository" (semantic + symbols vs. grep on a guessed name)

**Index (semantic search).** Top hits:
```
src/CTCM.API/CTCM.API.AppealCaseService/Repositories/AppealCaseRepository.cs:8-
src/CTCM.API/CTCM.API.AppealCaseService/Manager/AppealCaseManager.cs:22-676 
src/CTCM.API/CTCM.API.AppealCaseService/Repositories/IAppealCaseRepository.cs:6
src/CTCM.API/CTCM.API.AppealCaseService/Manager/AppealCaseManager.cs:486-623 
src/CTCM.API/CTCM.API.AppealCaseService/Manager/AppealCaseManager.cs:396-424 
```
The #1 hit is exactly `AppealCaseRepository.cs`, with `IAppealCaseRepository.cs` and `AppealCaseManager.cs` right behind it.

**Grep baseline** — an analyst who guesses the conventional name `AppealRepository`:
```
grep 'class AppealRepository' hits: 0
(0 — the real class is AppealCaseRepository; a wrong-name grep finds nothing)
```
**Delta.** Exact-name symbol lookup for the guessed `AppealRepository` also returns "No symbols found"; semantic search recovered from the imperfect query and surfaced the correct repository by intent. `symbols --name Appeal` (contains-match) then enumerates the whole appeal-case surface (AppealCaseManager, AppealCaseAssign, GetAppealPetition, SearchAppealCase, ...).

## Chunk-level coverage metric (Milestone 4 upgrade) — per-round behavior

Simulating the loop-until-dry accumulation the extract-rules workflow logs each round. Coverage is the chunk-level denominator that replaces the file-level `coveredAreas` heuristic. As rule citations accumulate, the claimed-chunk count climbs:
```
Round 1 (2 rules):  coverage: 23/58677 chunks claimed (0.0%); 58654 uncovered chunks (3 listed 
Round 2 (6 rules):  coverage: 134/58677 chunks claimed (0.2%); 58543 uncovered chunks (3 listed 
```
Claimed chunks climb 23 → 134 as citations accumulate — the per-round signal that steers the next round toward the highest-value uncovered chunks.

**Base/separator-tolerant path matching** (Decision Log 2026-07-01): a citation carrying the extractor's `legacy/<system>/...` prefix resolves to the same chunks as the repo-relative form:
```
legacy/ctcm-api/...SpecialClaimManager.cs:24-1640 -> coverage: 70/58677 chunks claimed (0.1%); 58607 uncovered chunks (1 listed 
(same 70 chunks as the repo-relative src/... form)
```

**JSON shape consumed by the workflow** (`coverage --json`):
```json
{
    "total": 58677,
    "claimed": 23,
    "uncovered": 58654,
    "pct": 0.03919764132453943,
    "uncovered_chunks": [
        {
            "chunk_id": "chunk:src/CTCM.API/CTCM.API.ClaimService/Dto/ClaimDtoFactory.cs:csharp:0:8be655e83b80",
            "path": "src/CTCM.API/CTCM.API.ClaimService/Dto/ClaimDtoFactory.cs",
            "start_line": 11,
            "end_line": 1010,
            "symbol": "ClaimDtoFactory"
        }
    ]
}
```

## Integration wiring & safety verification

- Both discovery agents keep `tools: Read, Glob, Grep, Bash` (no new tool grant):
```
agents/legacy-analyst.md:4:tools: Read, Glob, Grep, Bash
agents/business-rules-extractor.md:4:tools: Read, Glob, Grep, Bash
```
- All seven integration files reference `legacylift-search`:
```
README.md
agents/business-rules-extractor.md
agents/legacy-analyst.md
commands/modernize-assess.md
commands/modernize-extract-rules.md
commands/modernize-map.md
workflows/extract-rules.js
```
- `workflows/extract-rules.js` gates coverage on `args.repoRoot` — omitted ⇒ no coverage agent spawned, byte-identical to the prior grep/`coveredAreas` path (`node --check` passes):
```
205:  if (!repoRoot || citations.length === 0) return null
324:  if (repoRoot) {
459:  coverage: lastCoverage, // null when no index / repoRoot omitted; else final round's chunk-level coverage
```
- `tools/legacylift_search` full test suite: 171 passed (exit 0), including the 12 `test_coverage.py` cases.
