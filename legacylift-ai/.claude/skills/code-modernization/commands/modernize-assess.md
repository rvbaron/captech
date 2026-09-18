---
description: Full discovery & portfolio analysis of a legacy system — inventory, complexity, debt, relative scale
argument-hint: <system-dir> [--show-secrets] | --portfolio <parent-dir>
---

<!-- Modified by CapTech on 2026-09-14: issue the `tag-domains` ingest at the end of Step 6 instead of only describing it. The command authored `domains.json` and rendered ARCHITECTURE.mmd from the file, but nothing in the plugin ever ran `tag-domains`, so the knowledge store's `file_domains` was never populated on a documented run -- leaving `/modernize-map`'s fallback and `/modernize-extract-rules`' subject derivation reading an empty set. Also splits the single `exclude_globs` output into `exclude_globs` (first-party, not-a-business-capability) and top-level `vendored_globs` (third-party provenance), per docs/exec-plans/pending/layer0-extraction-gap-detection-decision.md SS3.K (Q27). Also: the Step 6 ingest now names the `py -3.12 -m legacylift_search.cli` fallback before allowing the conclusion that `legacylift-search` is unavailable -- a console script exiting with `ModuleNotFoundError` is a shim pointing at the wrong interpreter, not an absent tool, and treating it as absent silently skips the one step `map` and `extract-rules` both depend on. -->

**Mode select.** If `$ARGUMENTS` starts with `--portfolio`, run **Portfolio
mode** against the directory that follows. Otherwise run **Single-system
mode** against the system dir. Parse flags positionally-independently:
`--show-secrets` may appear before or after the system dir — the system
dir is the first non-flag token.

---

# Portfolio mode (`--portfolio <parent-dir>`)

Sweep every immediate subdirectory of the parent dir and produce a
heat-map a steering committee can use to sequence a multi-year program.

**Preferred — Workflow orchestration.** If the **Workflow tool** is available
in this session (this command invocation is your authorization), enumerate
the immediate subdirectories first — the workflow script has no filesystem
access — then launch one survey agent per system, all independent:

```bash
ls -d <parent-dir>/*/ | xargs -n1 basename   # bare subdir names, not paths
```

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/portfolio-assess.js",
  args: { parentDir: "<parent-dir>", systems: ["<sub1>", "<sub2>", ...] }
})
```

This is one agent per system (a 30-system estate = 30 agents — tell the user
the count before launching; the runtime queues them against its concurrency
cap). Each agent returns a structured metrics row and the workflow computes
COCOMO-II uniformly in code, so every row uses the identical formula. On
return, render `rows` (plus an "unmeasured" marker row for anything in
`unmeasured`) into the Step P4 heat-map, add the sequencing recommendation
yourself, and skip Steps P1–P3. For very long sweeps, note the workflow's
`runId` — if the session dies mid-sweep, relaunch with `resumeFromRunId` and
completed systems return instantly from cache.

**Fallback** (no Workflow tool): run Steps P1–P3 per system yourself, then P4.

## Step P1 — Per-system metrics

For each subdirectory `<sys>`:

```bash
cloc --quiet --csv <parent>/<sys>          # LOC by language
lizard -s cyclomatic_complexity <parent>/<sys> 2>/dev/null | tail -1
```

If `cloc`/`lizard` are not installed, fall back to `scc <parent>/<sys>`
(LOC + complexity) or `find` + `wc -l` grouped by extension, and estimate
complexity by counting decision keywords per file. Note which tool you used.

Capture: total SLOC, dominant language, file count, mean & max
cyclomatic complexity (CCN). For dependency freshness, locate the
manifest (`package.json`, `pom.xml`, `*.csproj`, `requirements*.txt`,
copybook dir) and note its age / pinned-version count.

## Step P2 — COCOMO-II complexity index

Compute the COCOMO-II basic figure per system: `2.94 × (KSLOC)^1.10`
(nominal scale factors). Show the formula and inputs so it is defensible,
not a guess.

**Use this only as a relative complexity/scale index** for ranking and
sequencing systems — bigger number = bigger, more complex estate. **It is
not a modernization timeline or cost.** The COCOMO person-month figure
assumes traditional human-team productivity; agentic transformation does
not follow those productivity curves, so do not present it (or convert it)
as how long the work will take or what it will cost. Label the column as an
index, not "person-months", and never attach a date or duration to it.

## Step P3 — Documentation coverage

For each system, count source files with vs without a header comment
block, and list architecture docs present (`README`, `docs/`, ADRs).
Report coverage % and the top undocumented subsystems.

## Step P4 — Render the heat-map

Write `analysis/portfolio.html` (dark `#1e1e1e` bg, `#d4d4d4` text,
`#cc785c` accent, system-ui font, all CSS inline). One row per system;
columns: **System · Lang · KSLOC · Files · Mean CCN · Max CCN · Dep
Freshness · Doc Coverage % · Complexity (COCOMO index) · Risk**. Color-grade the index and
Risk cells (green→amber→red). Below the table, a 2-3 sentence
sequencing recommendation: which system first and why.

Then stop. Tell the user to open `analysis/portfolio.html`.

---

# Single-system mode

Perform a complete **modernization assessment** of `legacy/$1`.

This is the discovery phase — the goal is a fact-grounded executive brief that
a VP of Engineering could take into a budget meeting. Work in this order:

## Step 1 — Quantitative inventory

Run and show the output of:
```bash
scc legacy/$1
```
Then run `scc --by-file -s complexity legacy/$1 | head -25` to identify the
highest-complexity files. Capture scc's COCOMO figure **only as a relative
complexity/scale index** — and **ignore scc's "Estimated Schedule Effort"
and cost-in-dollars lines**: those project a human-team timeline and budget,
which are invalid for agentic modernization (see the not-a-timeline note in
Step 6).

If `scc` is not installed, fall back in order:
1. `cloc legacy/$1` for the LOC table, then compute the COCOMO-II index
   yourself: `2.94 × (KSLOC)^1.10` (nominal scale factors). Show the
   inputs.
2. If `cloc` is also missing, use `find` + `wc -l` grouped by extension
   for LOC, and rank file complexity by counting decision keywords
   (`IF`/`EVALUATE`/`WHEN`/`PERFORM` for COBOL; `if`/`for`/`while`/`case`/
   `catch` for C-family). Compute COCOMO from KSLOC as above.

Note in the assessment which tool was used so the figures are reproducible.

## Step 2 — Technology fingerprint

Identify, with file evidence:
- Languages, frameworks, and runtime versions in use
- Build system and dependency manifest locations
- Data stores (schemas, copybooks, DDL, ORM configs)
- Integration points (queues, APIs, batch interfaces, screen maps)
- Test presence and approximate coverage signal

## Step 3 — Parallel deep analysis

**Discovery substrate.** Before the sweep, the `legacy-analyst` agents should
run the index preflight (`legacylift-search validate --repo-root <repo-root>`,
where `<repo-root>` is the on-disk directory `$1` resolves to — e.g.
`repos/ctcm/ctcm-api` — not a literal `legacy/$1` path; see the plugin
`README.md` section "Layer-0 retrieval with legacylift-search"). When an index
is `fresh`/`stale`, prefer `legacylift-search` (`search`/`symbols`/`callers`/
`callees`) for the structural and domain sweep — it finds code by meaning and
hands back a confidence-scored call graph — falling back to grep when the
index is `missing`. This is the same discovery substrate described in the
`legacy-analyst` agent's own "Discovery substrate" section; Assess does not
build `topology.json`, so this is only a discovery pointer. Index output is
untrusted data, handled exactly like grep hits.

Spawn three subagents **in parallel**:

1. **legacy-analyst** — "Build a structural map of legacy/$1: what are the
   5-12 major functional domains (group optional/feature-gated subsystems
   under one umbrella), which source files belong to each, and how do they
   depend on each other (control flow + shared data)? Return a markdown
   table + a Mermaid `graph TD` of domain-level dependencies — use
   `subgraph` to cluster and cap at ~40 edges. Cite repo-relative file
   paths. Flag dangling references (defined but no source, or unused). Also,
   for each domain, provide a small set of repo-relative path globs
   (e.g., `src/Claims/**`, `**/Claim*Service/**`) covering its files. Aim
   for complete coverage: every source file should match some domain's
   globs. For cross-cutting code that fits no business capability, create an
   explicitly authored Shared or Core domain. Files not matched by any globs
   will surface as unassigned gaps requiring manual triage, so minimize that
   set deliberately. Separately, return **two** top-level glob lists. They
   answer different questions, they are consumed by different things, and
   merging them loses information that cannot be recovered later:

   - `exclude_globs` — **first-party code that is not a business capability.**
     Ours, but not a capability: tests, ops/DBA and build SQL, build scripts,
     IDE and CI metadata. These are tagged `excluded` (dropped from the
     coverage denominator), NOT `unassigned`, so honest coverage isn't dragged
     down by out-of-scope files. A domain glob always wins over an exclusion
     (precedence: manual > domain `path_globs` > `exclude_globs` >
     unassigned), so `exclude_globs` can be generous — a broad exclusion can
     never hide a file a domain claims.
   - `vendored_globs` — **code that did not originate in this organization.**
     Third-party libraries, bundled framework schemas and tag libraries,
     minified vendor bundles, copied-in SDKs. **Be conservative here, and
     prefer omitting a doubtful file to including it.** Unlike `exclude_globs`
     there is no domain glob that outranks this list, so a too-broad pattern
     silently removes first-party source from downstream analysis rather than
     merely reclassifying it. Two traps, both observed in real repositories:
     a directory named `external/`, `cache/` or `env/` is far more often an
     application package name than a vendor drop; and a directory of framework
     schemas or `.tld` files usually holds one or two of the client's *own*
     alongside the vendored ones, so prefer naming the vendored files
     explicitly over globbing the directory.

   Do not put the same path in both lists. If a file is third-party it belongs
   only in `vendored_globs`; `exclude_globs` is for code we wrote and chose
   not to treat as a capability.
   **Glob syntax (all of `path_globs`, `exclude_globs` and `vendored_globs`):** globs are matched
   with gitignore semantics (pathspec GitWildMatch), so use `**`, `*`, `?`,
   and character classes — but NOT `{a,b}` brace expansion; write each
   alternative as its own entry (`config/hbm/standard/**`,
   `config/hbm/nonstandard/**`, …), never `config/hbm/{standard,nonstandard}/**`."

2. **legacy-analyst** — "Identify technical debt in legacy/$1: dead code,
   deprecated APIs, copy-paste duplication, god objects/programs, missing
   error handling, hardcoded config. Return the top 10 findings ranked by
   remediation value, each with file:line evidence. If evidence contains a
   credential value, mask it per your secret-handling rules — never quote
   it."

3. **security-auditor** — "Scan legacy/$1 for security vulnerabilities:
   injection, auth weaknesses, hardcoded secrets, vulnerable dependencies,
   missing input validation. Return findings in CWE-tagged table form with
   file:line evidence and severity. Mask every discovered credential value
   per your secret-handling rules — file:line plus a 2–4 character masked
   preview, never the value itself."

Wait for all three. Synthesize their findings.

## Step 4 — Production runtime overlay (optional)

If production telemetry is available — an observability/APM MCP server, batch
job logs, or runtime exports the user can supply — gather p50/p95/p99
wall-clock for the system's key jobs/transactions (e.g. JCL members under
`legacy/$1/jcl/`, scheduled batches, top API routes). Use it to:

- Tag each functional domain from Step 3 with its production wall-clock
  cost and **p99 variance** (p99/p50 ratio).
- Flag the highest-variance domain as the highest operational risk —
  this is telemetry-grounded, not a static-analysis opinion.

Include a small **Runtime Profile** table (Job/Route · Domain · p50 · p95 ·
p99 · p99/p50) in the assessment. If no telemetry is available, skip this
step and note the gap in the assessment.

## Step 5 — Documentation gap analysis

Compare what the code *does* against what README/docs/comments *say*. List
the top 5 undocumented behaviors or subsystems that a new engineer would
need explained.

## Step 6 — Write the assessment

**Secrets quarantine first.** The assessment gets shared and committed —
discovered credential values must never appear in it. If the
security-auditor found any hardcoded credentials:

1. Ensure `analysis/.gitignore` exists and contains the lines
   `SECRETS.local.md` and `*.local.patch` (create or append as needed —
   the patch pattern is used by `/modernize-harden`; writing both now
   means the ignore set is complete from first contact). If the project is a
   git repo, verify with `git check-ignore -q analysis/$1/SECRETS.local.md`
   — do not write any findings until the check passes. If there is **no
   git repo** (check for `.svn`/`.hg`/`CVS` too — a `.gitignore` protects
   nothing under another VCS): refuse `--show-secrets` and write
   `SECRETS.local.md` to `~/.modernize/$1/` instead of the project tree,
   telling the user where it went and why.
2. Write `SECRETS.local.md`: one row per credential — masked preview,
   `file:line`, credential type, what it grants access to,
   production/test guess, rotation recommendation. Only if the user passed
   `--show-secrets`, add the raw value column here — this file only, never
   ASSESSMENT.md.
3. Masking applies to **every section of ASSESSMENT.md**, whichever agent
   produced the finding — the Technical Debt section quotes hardcoded
   config; those quotes follow the same masking rule as Security Findings.
   The Security Findings section adds a one-line pointer:
   "Credential inventory in SECRETS.local.md (gitignored; not for sharing)."

Create `analysis/$1/ASSESSMENT.md` with these sections:
- **Executive Summary** (3-4 sentences: what it is, how big, how risky, headline recommendation)
- **System Inventory** (the scc table + tech fingerprint)
- **Architecture-at-a-Glance** (the domain table — **must list the identical
  domain set as `domains.json` below**: same domains, same names, same count;
  reference the diagram)
- **Production Runtime Profile** (the runtime table from Step 4 with the highest-variance domain called out — or "no telemetry available")
- **Technical Debt** (top 10, ranked)
- **Security Findings** (CWE table)
- **Documentation Gaps** (top 5)
- **Relative Scale** (the COCOMO-II index + KSLOC as a complexity/scale signal for ranking this system against others. **Not a timeline:** state plainly that this is a relative size measure, not an estimate of how long modernization will take or what it will cost — it assumes traditional human-team productivity, which agentic transformation does not follow. Do not print person-months, a schedule, a cost, or a date.)
- **Recommended Modernization Pattern** (one of: Rehost / Replatform / Refactor / Rearchitect / Rebuild / Replace — with one-paragraph rationale, and the command it routes to: **Replatform / Refactor-in-place same-stack version bump → `/modernize-uplift`**; Rearchitect/cross-stack → `/modernize-transform`; Rebuild → `/modernize-reimagine`)

Also create `analysis/$1/domains.json` containing the domain and edge data in machine-readable form:

```json
{
  "schema_version": 1,
  "assess_run_id": "<ISO-8601 timestamp>-<system>",
  "domains": [
    {
      "domain_id": "claims-management",
      "name": "Claims Management",
      "description": "Intake, adjudication, and reserve handling for claims.",
      "path_globs": ["src/CTCM.API.Claim*/**", "**/Claim*Service/**"]
    }
  ],
  "edges": [
    {"from": "workflow-orchestration", "to": "claims-management", "kind": "calls", "evidence": "WorkflowService invokes ClaimService (11 clients)"}
  ],
  "exclude_globs": ["**/test/**", "**/*Tests/**", "db/migrations/**", "**/generated/**"],
  "vendored_globs": ["**/wwwroot/lib/**", "**/Scripts/jquery-*.js", "third_party/**"]
}
```

Where `domain_id` is a kebab-case slug of the domain name, `path_globs` come
from the first legacy-analyst's per-domain globs, and `edges` mirror the
dependency arrows in the analyst's Mermaid diagram. `exclude_globs` and
`vendored_globs` are optional **top-level** arrays (siblings to
`domains`/`edges`, NOT `domains[]` entries).

`exclude_globs` holds the analyst's **first-party not-a-capability** globs:
files matching one of these and no domain glob are tagged `excluded` and
dropped from the coverage denominator, rather than surfacing as `unassigned`
gaps. `vendored_globs` holds **third-party provenance** — code that did not
originate in this organization. The two are deliberately separate: a file can
be out of scope for capability tagging *because* it is a test we wrote, or
*because* it is somebody else's library, and only the second fact tells a
downstream consumer that the file is not ours to analyze at all. Merging them,
as earlier versions of this command did, makes the distinction unrecoverable.

`vendored_globs` is additive and ignored by readers that predate it, so emitting
it is safe against any existing tooling. Write all of `path_globs`,
`exclude_globs` and `vendored_globs` with gitignore syntax — no `{a,b}` brace
expansion; one entry per alternative (see the Step 3 subagent instruction).

**Single domain set.** The Architecture-at-a-Glance table (Step 6 sections) and
this `domains.json` are two renderings of **one** domain list — the first
legacy-analyst's domains. Author that list once and produce both from it:
every domain in the prose table must have exactly one `domains[]` entry and
vice versa (same names, same count). This is the set that flows downstream —
`tag-domains` ingests `domains.json` into `knowledge.sqlite`, and
`/modernize-map` groups its topology by these same `domain_id`s — so a table
that drifts from `domains.json` would fork the domain set across the pipeline.
**`exclude_globs` is not part of this set:** exclusions are not domains, so they
get no `domains[]` entry and no Architecture-at-a-Glance row — they live only in
`domains.json`. Do not add an "Excluded" row to the prose table to "match"
`domains.json`; the 1:1 table↔`domains[]` correspondence is intentional.

Render `analysis/$1/ARCHITECTURE.mmd` from that `domains.json` by shelling out
to the renderer — do not hand-author or copy out the legacy-analyst's Mermaid:

```
legacylift-search render-architecture --domains "analysis/$1/domains.json" --output "analysis/$1/ARCHITECTURE.mmd"
```

Note the absence of `--repo-root`: `$1` here is the assess system-dir name,
not the resolved `legacylift-search` repo-root Step 3 defines, and the
`--domains` render path never touches the knowledge database, so
`--repo-root` would be both wrong and unnecessary.

**Then ingest the set into the knowledge store — this step is not optional
and nothing downstream does it for you:**

```
legacylift-search tag-domains --domains "analysis/$1/domains.json" --repo-root <repo-root>
legacylift-search render-architecture --repo-root <repo-root> --output "analysis/$1/ARCHITECTURE.mmd"
```

Here `--repo-root` **is** required — both commands write to and read from
`knowledge.sqlite`, so they need the resolved repo-root from Step 3, not `$1`.
`tag-domains` resolves each domain's `path_globs` to per-file domain rows and
stamps the Chroma metadata; the second `render-architecture` (note: no
`--domains`) then regenerates `ARCHITECTURE.mmd` authoritatively from the
durable tagged data rather than from the file on disk. `/modernize-map` groups
its topology by this same set and `/modernize-extract-rules` derives each
requirement's subject from it, so **skipping this leaves both reading a set
nothing ingested**.

**Before concluding `legacylift-search` is unavailable, try the fallback.** A
console script that exits non-zero with `ModuleNotFoundError` is not an absent
tool — it is a shim resolving into an interpreter that lacks the package, which
is common on a machine with several Pythons. Run the same subcommand as:

```
py -3.12 -m legacylift_search.cli tag-domains --domains "analysis/$1/domains.json" --repo-root <repo-root>
```

Only if *that* also fails is the tool genuinely unavailable. Then say so plainly
in your output and name both commands as the step to run once it is —
`domains.json` on disk is still correct, and `map` falls back to reading it
directly. Do not report a degraded run as a clean one.

## Step 7 — Present

Tell the user the assessment is ready and suggest:
`glow -p analysis/$1/ASSESSMENT.md`
