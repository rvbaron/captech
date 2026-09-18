# Refresh NNG Analysis — Session Handoff

> ## Status: COMPLETE — closed 2026-08-05. All three reopened items resolved.
> The stated scope (`preflight` → `assess` → `tag-domains` → `map`, "at least as far as map")
> completed on both systems 2026-08-04 and all artifacts validate. The three decisions that
> reopened this plan on 2026-08-04 are now closed:
>
> | Item | Resolution |
> |---|---|
> | **A** — restore a named security domain? | **No.** Measured, not judged: the app's Security Findings carry 63 citations across 53 files and **0** land in the 11-file security package; the DB's carry 9 of 43 across 6 of 28 files. Domain sets are final at 12 (app) / 11 (DB), 100% coverage, 0 ambiguity. [§0-A](#a--the-security-domain-question-closed-2026-08-05) |
> | **B** — rotate the 15 app credentials | **Out of scope.** Review-only engagement; reported, not remediated. Findings **not** retracted — assume all 15 live. [§0-B](#b--credential-rotation-closed-2026-08-05-out-of-scope) |
> | **C** — the `pleaud` permission model | **Closed as an external dependency.** Not answerable from this repository at any effort. The query to hand to the client/DBA is recorded in [§0-C](#c--the-pleaud-question-closed-2026-08-05-external-dependency), along with what each answer implies. |
>
> **Nothing in this plan is executable by us any more.** Read it as the record of what was run,
> what was found, and what was corrected. Its §3 (corrections), §4 (environment traps), §5/§6
> (results) and §11 (reproduction) remain useful reference.
>
> **Do not re-run the pipeline.** `repos/nng-app-legacylift-analysis/` is gitignored
> ([§7](#7-nothing-is-in-git)) — the analysis outputs are on-disk only and not recoverable if
> overwritten. `/modernize-assess` in particular would destroy validated `ASSESSMENT.md`,
> `domains.json` and `ARCHITECTURE.mmd` for both systems.

**Engagement posture:** this was a **review-only** exercise against a codebase we are
authorized to read. **No changes were made to NNG code, configuration, or credentials, and no
remediation action was taken.** Findings are reported; acting on them is the owner's decision.
This is why item B is closed rather than tracked.
**Pipeline:** `preflight` → `assess` → `tag-domains` → `map` executed on both systems ✅
**Started:** 2026-08-03 · **Pipeline completed:** 2026-08-04 · **Reopened:** 2026-08-04
**Branch:** `feature/version-next` @ `52ff57c7` (no repo code changes by this effort —
see [§7](#7-nothing-is-in-git))

Companion handoff for the reopened scope:
[`SESSION-HANDOFF-nng-open-items-2026-08-04.md`](./SESSION-HANDOFF-nng-open-items-2026-08-04.md)

---

## 0. Decisions — all closed 2026-08-05

Originally the three reopened items; all now resolved. **Nothing in this plan is outstanding.**

| # | Item | Type | Blocking what | Detail |
|---|---|---|---|---|
| ~~**A**~~ | ~~Restore a named security domain?~~ **CLOSED 2026-08-05 — no.** Domain sets stay at 12 (app) / 11 (DB), 100% coverage, 0 ambiguity. | Decided | Nothing. `domains.json` is unchanged, so no re-tag and no `map` re-run. | [§0-A](#a--the-security-domain-question-closed-2026-08-05) |
| ~~**B**~~ | ~~Rotate the 15 app credentials.~~ **CLOSED 2026-08-05 — out of scope, not tracked.** Review-only engagement: the credentials are **reported, not remediated**. The findings stand. | Decided | Nothing. | [§0-B](#b--credential-rotation-closed-2026-08-05-out-of-scope) |
| ~~**C**~~ | ~~Answer the `pleaud` permission question.~~ **CLOSED 2026-08-05 — external dependency.** Unanswerable from this repository; the query is recorded for whoever has server access. The DB assessment's audit-integrity findings stand as stated, with the severity caveat noted below. | Decided | Nothing on our side. | [§0-C](#c--the-pleaud-question-closed-2026-08-05-external-dependency) |

### A — the security-domain question (CLOSED 2026-08-05)

**Decision: do not restore. `domains.json` is unchanged in both systems.** Recorded here with
the evidence so the item is not reopened without new data.

The prior app set had a `security-access-control` domain (11 files); the prior DB set had a
`security` domain (28 files — role/schema DDL scripts, **zero tables**). Neither survived
re-derivation:

- **App:** `service/security/**`, `persistence/security/**` → `shared-core-platform`;
  `model/external/{NngUser,SecUser}.java` → `external-system-integration`.
- **DB:** `Security/Roles/*`, `Security/Schemas/*` → `shared-core-platform-reference`.

#### The measurement that settled it

Each system's **Security Findings** section was tested for citations landing inside the prior
security domain (matched on basename, so partial-path citations still count):

| | citations in Security Findings | landing inside the prior security domain |
|---|---:|---:|
| app | 63 across 53 files | **0** |
| DB | 43 across 31 files | **9**, across 6 of 28 files |

The app's zero is not a matching artifact. The findings are *about* access control but cite
the **enforcement sites**, which live in the business domains — CWE-266 "the role model
collapses" (`ASSESSMENT.md:232`) cites `AbstractEdiDao.java:37,47`, `PoifarmTapDao.java:40`,
`PoipointDao.java:52`, `spring-security.xml:19`; finding 10 cites `SecurityAdvice.java:54`
but carries its weight on `HealthCheckService.java` and `FilterConfig.java:35-40`. A
`security-access-control` domain would collect 1,092 LOC of widely-consumed plumbing
(`SecurityRoles.java` is 22 lines with **22 inbound referencers**) and contain none of the 23
findings — addressable-looking in `map` and `brief`, but not where the work is.

The DB case was stronger but still thin: 223 LOC total, **13 of 28 files are 3-line bare
`CREATE ROLE` stubs with no grants**, 20 of 28 are ≤7 lines, and only 5 files carry any grant
at all (7 `GRANT SELECT`, 4 each `UPDATE`/`INSERT`/`EXECUTE`/`DELETE`, **zero `DENY`**). The
one substantive file, `Security/Roles/dboSelect.Role.sql:4-27`, is the 12-role schema-wide
`GRANT SELECT` Critical — already cited, and reachable by path without a domain container.

#### Two traps this avoided, worth keeping on record

1. **Companion handoff §3.1's candidate list was incomplete.** An app carve-out must also
   pull `NngUser.java` and `SecUser.java` out of `external-system-integration` — §3.1 lists
   only shared/core paths, so following it verbatim would have left two files double-matched,
   which is exactly the ambiguity re-derivation eliminated.
2. **Security is cross-cutting here, not a capability.** The 12/11 sets stay at 100% coverage
   / 0 ambiguity ([§8](#8-domain-drift)).

**If the need resurfaces**, the right instrument is a named cross-cutting *section* in each
`ASSESSMENT.md` indexing findings by enforcement site — not a domain. The mechanical steps
for a domain edit remain in companion handoff §3 should that judgement ever be revisited.

### B — credential rotation (CLOSED 2026-08-05, out of scope)

**Decision: not our action, not tracked here.** This is a review-only exercise on a codebase
we are authorized to read. In a real engagement rotating these 15 credentials would be the
first remediation item and we would drive it; here we are not making changes to NNG, so the
item is closed rather than carried as open work.

**What closing B does *not* mean.** The credentials are real and the findings are not
retracted — they remain in `ASSESSMENT.md` and in
`analysis/customer.ple.nng.app/SECRETS.local.md` (gitignored, all values masked) as reported
findings. "Closed" means *no rotation will be performed or chased by us*, not "resolved" and
not "benign." If this analysis is ever handed to NNG, the two facts to lead with are:

- a committed **PKCS#12 private key** reused across both applications *and* configured as the
  truststore, and
- one Hazelcast group password **byte-identical across dev/QA/model-office/prod**, so a
  compromise in any lower environment is a production compromise.

Rotation order (widest blast radius first) stays documented in `SECRETS.local.md`, with the
Azure DevOps PAT first because a write-scoped feed token reaches every NNG application, not
just PLE. That ordering is advice for the owner, not a task list for us.

**Nothing was ever gated on this**, so closing it changes no sequencing:
`/modernize-harden` was never deferred pending rotation.

### C — the `pleaud` question (CLOSED 2026-08-05, external dependency)

**Closed because it is not answerable from this repository at any level of effort** — it needs
a live server. Do not let a future session try to infer it from the export, and do not let a
subagent guess. Everything needed to answer it is recorded below; the DB `ASSESSMENT.md`
CWE-284 row stands as written, with the severity caveat at the end of this section.


72 audit `INSERT`s from 54 triggers on 18 tables write into `pleaud`, which has no DDL in the
tree and **no grants anywhere in this repository**. Two configurations are possible and they
have opposite security outcomes:

- **Ownership chaining on** → triggers write as `dbo`; audit integrity then depends on a
  server/database setting that is invisible to source control.
- **Chaining off** → the application roles themselves hold `INSERT` on the audit tables, so
  any principal that can trigger an audit write can also **forge arbitrary audit rows**, and
  possibly `UPDATE`/`DELETE` existing ones.

#### The queries to hand to the client/DBA

Three, not one — the per-database flag alone does **not** settle it.

```sql
-- 1. per-database flags
SELECT name, is_db_chaining_on, is_trustworthy_on FROM sys.databases;

-- 2. server-level override. If this is on, chaining is enabled for EVERY database and
--    is_db_chaining_on from query 1 is ignored. Omitting this misreads query 1.
SELECT name, value_in_use FROM sys.configurations
WHERE name = 'cross db ownership chaining';

-- 3. what the application roles actually hold in the audit database
USE pleaud;
SELECT dp.name AS principal,
       p.permission_name,
       p.state_desc,                       -- GRANT / DENY / GRANT_WITH_GRANT_OPTION
       COALESCE(OBJECT_SCHEMA_NAME(p.major_id) + '.' + OBJECT_NAME(p.major_id),
                '(database-wide)') AS securable
FROM sys.database_permissions p
JOIN sys.database_principals dp ON dp.principal_id = p.grantee_principal_id
WHERE dp.name LIKE 'Member%'
ORDER BY dp.name, securable, p.permission_name;
```

**Severity caveat to apply once the answer is known:** if chaining is off and the roles hold
`INSERT` directly, the caller-supplied-audit-actor finding (**121 of 337 procs**) escalates
from High to effectively **Critical** — the trail becomes forgeable rather than merely
untrustworthy. The DB `ASSESSMENT.md` states the finding at High; that is the correct reading
*absent* the answer, not a conclusion that the lower severity holds.

Target state either way: audit tables grant `INSERT` **only**, to a principal the applications
cannot assume, with `DENY UPDATE, DELETE` to all application roles.

**Two adjacent questions for the same person**, worth asking in one conversation: can the
`pleaud` and `nngple` schemas be obtained (18 shadow tables must version in lockstep with 18
masters, and nothing currently constrains them), and do SQL Agent job definitions exist
upstream (without them the 43 DB entry points in `topology.json` are inferred from naming
families, not an inventory).

---

## 1. What this effort was

Re-run the local `code-modernization` plugin pipeline against the NNG codebase from a
**cleared** analysis folder, going **at least** as far as `/modernize-map`.

- **Target:** `repos/nng-app-legacylift-analysis/`
- **Code under analysis:** `legacy/`, holding **two systems**:
  - `legacy/customer.ple.nng.app` — Java/Gradle web application
  - `legacy/customer.ple.nng.db.ETSPii` — SQL Server T-SQL script repository
- **Output:** `repos/nng-app-legacylift-analysis/analysis/<system>/`

Three sibling folders hold *prior* runs and remain on disk as reference —
`analysis-original/`, `analysis-domains-enhanced/`, `analysis-semantic-search-enhanced/`.
Nothing was written into them.

---

## 2. Pipeline state — complete

All artifacts validate. **Do not re-run these** — a re-run overwrites good output.

| Step | System | Status |
|---|---|---|
| `/modernize-preflight` | both | ✅ DONE 2026-08-03 |
| `/modernize-assess` | both | ✅ DONE 2026-08-04 |
| `tag-domains` (re-tag) | both | ✅ DONE 2026-08-04 |
| `/modernize-map` | both | ✅ DONE 2026-08-04 |
| anything after `map` | both | ⬜ out of stated scope |

The one exception that *would* have forced a re-run — §0 item A — was
[closed "no" on 2026-08-05](#a--the-security-domain-question-closed-2026-08-05), so
`domains.json` is unchanged and **nothing needs re-tagging or re-mapping**.

### Artifacts on disk

```
analysis/
├── .gitignore                              (pre-existing)
├── customer.ple.nng.app/
│   ├── PREFLIGHT.md  ASSESSMENT.md  SECRETS.local.md (gitignored)
│   ├── domains.json  ARCHITECTURE.mmd
│   ├── topology.json  TOPOLOGY.html  extract_topology.py
│   └── call-graph.mmd  data-lineage.mmd  critical-path.mmd
└── customer.ple.nng.db.ETSPii/
    ├── PREFLIGHT.md  ASSESSMENT.md         (no credentials exist → no SECRETS file)
    ├── domains.json  ARCHITECTURE.mmd
    ├── topology.json  TOPOLOGY.html  extract_topology.py
    └── call-graph.mmd  data-lineage.mmd  critical-path.mmd
```

### Decisions taken by the user (2026-08-04)

- **Domain sets: re-derived from scratch**, not reused. Drift reported in [§8](#8-domain-drift).
- **App Git mirror: not available.** Risk ranking is therefore complexity- and
  coupling-driven in both assessments; this is stated as a limitation, not a formality.

---

## 3. ⚠️ Corrections to this document's own earlier findings

**The §5 items below were wrong in the 2026-08-03 version of this file.** Each was
re-verified mechanically. Anyone reading the old numbers will draw wrong conclusions.

### 3.1 §5.4 — the DB trigger count was understated

| | claimed | **verified** |
|---|---:|---:|
| Trigger-bearing tables | 16 | **18** |
| DML triggers | 16 | **54** (`td_`/`ti_`/`tu_` per table) |
| `pleaud` audit INSERTs | — | **72** (4/table; all 72 lack a column list) |

**Cause:** 16 files write `create trigger` (one space); **two write `CREATE  trigger`
with a double space**, so a single-space pattern misses them. The two missed tables are
the most important ones — **`dbo.LESLegalEntity`** (`:38,90,143`, the party master
holding cleartext [redacted]) and **`dbo.POIPoint`** (`:28,71,114`).
Corpus lesson: match `CREATE\s+TRIGGER`, case-insensitive, comments stripped.

### 3.2 §5.5 — the two "broken references" are **not bugs**

`pleaud..poistaushistory` and `pleaud..lesstatushitory` are **comment-only**, inside
`/* */` `data table accessed` headers. The executable code in the same files is correctly
spelled (`up_process_PI_POISTAT:10` is the comment; `:50`,`:87` are correct). **They can
never raise "invalid object name."** There are at least **five** of this class, not two
(also `POISatusHistory`, `POIPetroleumInstitudeGrid`, `POISurveyStandart`).
→ Reclassified: documentation drift, **not** an `extract-rules` adjudication item. The
real finding is that the `data table accessed` manifests are unreliable (3 of 16 name a
non-existent table), so lineage must come from executable statements only.

### 3.3 §5.3 — external-database claims were wrong in three ways

Verified by masking comment regions, then counting (both elided `db..obj` **and**
bracketed/3-part forms):

| DB | executable refs | files | form | verdict |
|---|---:|---:|---|---|
| `pleaud` | 97 | 29 | `db..obj` | real, highest-traffic |
| `nngple` | 17 | 1 | `db..obj` | real |
| `etscontracts` | 2 | 2 | `db..obj` | real |
| `etssec` | 1 | 1 | **3-part `db.schema.obj`** | real |
| `dba` | 1 | 1 | bracketed 3-part | real, in excluded scaffolding |
| `edsintfc` | **0** | 0 | — | **comment-only, not a dependency** |
| `etspii` (self) | 733 | 226 | both | not external — hardcoded self-name |

1. **`edsintfc` is not a real dependency** — 4 external DBs carry logic, not 5.
2. **A 6th DB exists that §5.3 omitted** — `dba` (release tracking).
3. **"All use the elided form" is false** — `etssec` uses proper 3-part naming, so a
   parser tuned *only* for `db..obj` misses it. Handle both.

### 3.4 §5.1 — the prior run's metrics were **not** inflated

§5.1 claimed "the prior run missed this… prior-run metrics are inflated." It did not.
`analysis-domains-enhanced/customer.ple.nng.app/ASSESSMENT.md:15-23` already reports
bin-excluded figures (Java 995 / 97,239; Total 1,542 / 168,149) and even labels
JavaScript "mostly vendored libs". A fresh `scc` gives 1,541 / 168,026 — a trivial delta.

What the prior run actually lacked was `bin/**` in `exclude_globs`, and that was
**harmless**: `bin/` was never indexed (`repo_files` = 1,229 rows, **zero** matching
`bin/`). So §8's "one correction that improves on the prior run" was a documentation
nicety, not a metrics fix. The globs were added anyway, since declaring them is correct.

**However, `PREFLIGHT.md`'s *module table* IS inflated** (a different table from the
`scc` one): it lists **356** JSPs for `ple-web`; the true figure is **178**, the other 178
being byte-identical `bin/` duplicates. Repo-wide JSP total is 186, which reconciles with
`scc`. Corrected in the new `ASSESSMENT.md`.

### 3.5 §6 — the security list was materially incomplete

§6 listed 3 items (PAT, property files, partial principal graph). Actual state:

- **The app has 15 credentials in tracked source**, inventoried in `SECRETS.local.md`
  (gitignored, masked). Includes a **committed PKCS#12 TLS private key** reused across
  both applications and also configured as the truststore, and one Hazelcast group
  password **identical across dev/QA/model-office/prod** (13 SHA-256-identical files).
- **§6 omitted a Critical the *prior run had already found***: two production LDAP/AD
  service-account bind passwords at `ple-arch-properties/JavaSource/config/ldapConfig.xml:9,18`
  (`analysis-domains-enhanced/.../ASSESSMENT.md:78`). Verified still present.
- **Three further Criticals surfaced:** unauthenticated `jamon-web` SQL/log4j console
  shipped in the EAR; Spring Web Flow 2.4.1 with `model=` and **no `<binder>` in any of
  33 flows** (the CVE-2017-4971 RCE configuration); and an arbitrary-file-read/exfiltration
  chain exploitable by a *read-only* user via the same unrestricted binding.
- **The DB has zero credentials** — explicit verified negative across 568 `.sql` files.

**No rotation has been confirmed for anything.** Assume all 15 are live.

---

## 4. Environment — corrections

Everything in the 2026-08-03 tool table still holds (`scc` 3.7.0 confirmed working, not
re-blocked). Two additions:

1. **`legacylift-search` on PATH is BROKEN** — `ModuleNotFoundError: legacylift_search`
   (the shim under `Python314\Scripts` points at an interpreter without the package).
   Use the venv binary:
   `tools/legacylift_search/.venv/Scripts/legacylift-search.exe`
   (and its `python.exe` for anything needing `pathspec`). `render-architecture` and
   `tag-domains` both need this.
2. **Clearing `analysis/` did NOT clear domain state.** The durable knowledge store lives
   at `legacy/<system>/legacylift-docs/knowledge/knowledge.sqlite` — deliberately outside
   the gitignored index dir and never touched by `--reset`. Both indexes were still
   `fresh` and still tagged with the *prior* domain sets. **`tag-domains` must be re-run
   after any new `domains.json`**, or `map` groups by stale IDs. Done here; the tool
   reported dropping all 8 stale domains per system with reclassification counts.

### Gotchas (carried forward, still true)

`grep -P` unsupported; use `sed -E`. Bash needs absolute `/c/Users/...` paths. Beware
`grep -o 'table="..."'` matching inside `mutable="false"`. Always exclude `*/bin/**` when
counting the app. **New:** a bash heredoc mangles `'\\'` in embedded Python — use
`chr(92)`. **New:** `sqlite3.connect` *creates* a missing file; a probe accidentally
created a 0-byte `knowledge.sqlite` in the app index dir (deleted, index re-validated).

---

## 5. Assess results — headlines

Full detail in each `ASSESSMENT.md`.

| | `customer.ple.nng.app` | `customer.ple.nng.db.ETSPii` |
|---|---|---|
| Size | 1,541 files / 168,026 code | 571 files / 27,299 code |
| COCOMO-II scale **index** (not a timeline) | **825** | **112** |
| Domains | 12 | 11 |
| Coverage | 100% (846 assigned / 383 excluded / 0 unassigned) | 100% (565 / 3 / 0) |
| Pattern | **Refactor**, gated on build + persistence | **Refactor**, no-code hardening first |
| Routes to | `/modernize-uplift` (after prerequisites) | `/modernize-uplift`; `extract-rules` higher value |

**App gate item:** Hibernate 3.3.2.GA (2009) + Spring ORM 3.1.0 force-pinned into Spring
Boot 2.7.5; 58 files use the Criteria API Hibernate 6 removed. Nothing strategic proceeds
around it — and **the build does not run**, so no finding is runtime-verified and none of
the 332 test classes can execute.

**DB headline:** the highest-value sweep came back **clean — 0 of 337 procs build dynamic
SQL**. Risk is access control, audit integrity, and portability instead: cleartext
[redacted] details behind a single schema-wide `GRANT SELECT` held by 12 roles; the
audit actor is a **caller-supplied parameter in 121 of 337 procs**; `LESWireTransfer`
has **no audit trigger at all**; and the DB hardcodes its own name **733
times across 226 files**, blocking Azure SQL and any rename/clone.

**Available scope reduction:** **181 of 337 DB procs have no caller** (Hibernate
superseded them; only 8 procs are app-bound). Confirm empirically with
`sys.dm_exec_procedure_stats` over a full business cycle **before** estimating migration.

---

## 6. Map results

Both `topology.json` files validate: 0 dangling edge endpoints, all ids resolve,
`dom:excluded` present, 0 unassigned, 7 observations, 4 persona flows each, leak scan
clean (no URLs/credentials — the index's `evidence` column carries live config values and
is read only to classify read-vs-write, never emitted).

| | app | DB |
|---|---:|---:|
| Modules / datastores | 1,229 / 137 | 568 / 153 |
| Edges | 8,519 (7,969 call · **296 dispatch** · 237 read · 17 write) | 868 (76 call · 690 read · 102 write) |
| Entry points | 53 | 43 (**inferred** — no SQL Agent jobs exported) |
| Dead-end candidates | 33 (97 suppressed) | 295 (194 suppressed) |

**Two findings worth carrying forward:**

1. **The index cannot produce `dispatch` edges.** It binds a target at confidence
   0.7/0.85 or not at all — there is no low-confidence *bound* edge. Left alone, the
   entire framework binding layer is invisible and its ~60 string-bound targets look
   dead. All 296 app dispatch edges were resolved **from config** (Web Flow SpEL bean
   names, the `model=`→`…Validator` naming convention, Quartz `jobClass`,
   servlet/filter/listener and `.tld` class elements). This is `/modernize-map` principle
   #1 in practice, and it cut dead-end candidates from 58 → 33.
2. **The DB's 295 dead-end candidates are a stronger claim than the app's 33.** There is
   no dynamic SQL anywhere, so a proc with no inbound edge provably has no caller *inside
   this repository* — but external callers (SSIS, SQL Agent, reporting, other apps) still
   cannot be excluded. That is why they are candidates, and why finding #1 in the DB
   assessment insists on empirical confirmation before dropping anything.

`extract_topology.py` (identical in both dirs) is re-runnable and auditable; it pins
domain containers to `domains.json` and never re-derives domains.

---

## 7. Nothing is in git

`repos/nng-app-legacylift-analysis/` is gitignored at `.gitignore:92`. All analysis
outputs are **untracked, on-disk only, not recoverable if deleted**. `git status` stays
clean regardless of what this effort writes. This file is the only tracked artifact.

The app has **no version history at any level** (no `.git`, 0 files tracked by the
parent), and the user confirmed no upstream mirror is available. `ETSPii` has its own
`.git` — 22 commits 2022–2025, last 2025-06-11 — but they are bulk export commits
describing export cadence, not code churn, so risk ranking is complexity-driven for both.

---

## 8. Domain drift

Measured against the **index** file universe (the denominator `tag-domains` uses), not an
on-disk walk:

| | app prior | app new | DB prior | DB new |
|---|---:|---:|---:|---:|
| Domains | 10 | **12** | 8 | **11** |
| Assigned / excluded / unassigned | 846 / 383 / 0 | 846 / 383 / 0 | 568 / 0 / 0 | 565 / 3 / 0 |
| Coverage | 100% | 100% | 100% | 100% |
| **Ambiguous (file → >1 domain)** | **24** | **0** | **71** | **0** |

**Coverage was already 100% in both prior runs — re-deriving did not improve it.** The
two real gains:

1. **95 ambiguous assignments eliminated.** The prior DB set had **53 files matching both
   `legal-entity-party-les` and `point-pipeline-poi`**, including all 83 `up_GAS_*` procs.
   Since `map` groups topology by `domain_id`, ambiguity means unstable bucketing.
2. **Capabilities that were previously merged now have their own domains** — not renames:
   - **DB `gas-operations-query-api` (102 files)** is entirely new; the prior 8-domain set
     had *no home for the read/inquiry surface* (~30% of the estate).
   - **DB `partner-application-views-extracts` (32 files)** is new; per-consumer
     projections were scattered across three prior domains.
   - **DB** `farm-tap-management`, `pipeline-topology-linear-assets`,
     `survey-grid-geographic-reference` split out of the monolithic `point-pipeline-poi`.
   - **App** `search-lookup`, `batch-scheduling`, `point-grouping-ownership`,
     `farm-tap-regional-ops` are new; the rest are renames. Only
     `external-system-integration` and `shared-core-platform` kept their IDs.

**Resolved 2026-08-05:** the re-derivation **dropped the named security domain** in both
systems (app `security-access-control` → `shared-core-platform` + `external-system-integration`;
DB `security` → `shared-core-platform-reference`). The user decided **not** to restore it —
the app's 23 security findings cite **0 of** those 11 files, and the DB's cite 6 of 28. Full
rationale in [§0-A](#a--the-security-domain-question-closed-2026-08-05). These domain sets are
final.

---

## 9. Open questions — all closed or carried out of scope

**Answered 2026-08-04:** domain sets re-derived (not reused); no app Git mirror exists.
**Answered 2026-08-05:** the named security domain is **not** being restored — the 12/11 sets
are final ([§0-A](#a--the-security-domain-question-closed-2026-08-05)).

**Not tracked (review-only scope):** credential rotation. No rotation is confirmed for any of
the 15 credentials and none will be pursued by us — see
[§0-B](#b--credential-rotation-closed-2026-08-05-out-of-scope). Assume all 15 are live.

### Carried out of this plan — questions only the client can answer

None of these is actionable by us; all are closed as **external dependencies**, not as
answered. They are the standing ask-list if the engagement ever resumes with server access or
an SME. The first three need a DBA; the last needs an application SME.

- **What is the `pleaud` permission model?** Was item C — the three queries and the severity
  consequence are in [§0-C](#c--the-pleaud-question-closed-2026-08-05-external-dependency).
  Either ownership chaining is on (audit integrity depends on a setting invisible to source
  control) or the app roles hold `INSERT` directly (audit rows can be forged). Opposite
  outcomes; unanswerable from the export.
- **Can the `pleaud` and `nngple` schemas be obtained?** 18 shadow tables must version in
  lockstep with 18 masters and nothing constrains them.
- **Do SQL Agent job definitions exist upstream?** Without them the 43 DB entry points
  are inferred from naming families, not an inventory.
- **What else connects to `etspii`?** Needed before dropping the 181 uncalled procs — and the
  DB assessment's scope-reduction claim rests on it, so it should not be quoted as a saving
  until confirmed with `sys.dm_exec_procedure_stats` over a full business cycle.
- **Why is `FilterConfig.java:35-40` (Spring Security chain) commented out?** Intentional
  given `nng-authorization` 4.0.1, or an unintended regression?

---

## 10. Out of scope (unchanged)

`harden`, `transform`, `uplift`, `reimagine`, `brief`. The user asked for "at least"
`map`; that is done. `/modernize-harden` is the natural next step for the app (it
formalizes 23 security findings into a reviewable patch); for the DB,
`/modernize-extract-rules` is higher value, since 337 procs and 51 views are where the
business logic lives.

**One scoping note for `extract-rules`:** do **not** ask it to adjudicate the two
"misspelled references" as the 2026-08-03 plan suggested — that item is closed as
comment-only drift (§3.2).

---

## 11. Reproducing the derived numbers

`extract_topology.py` reproduces all topology figures. For the rest:

```bash
ROOT=/c/Users/dnorton/captechdev/legacylift-ai/repos/nng-app-legacylift-analysis
LLS=/c/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/legacylift-search.exe
PY=/c/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe

# --- inventory (note the excludes) ---
scc $ROOT/legacy/customer.ple.nng.app --exclude-dir .git,legacylift-docs,.gradle,.settings,bin
scc $ROOT/legacy/customer.ple.nng.db.ETSPii --exclude-dir .git,legacylift-docs

# --- index + domain state ---
cd $ROOT && "$LLS" validate --repo-root legacy/customer.ple.nng.app

# --- DB triggers: MUST allow multiple spaces, strip comments first ---
cd $ROOT/legacy/customer.ple.nng.db.ETSPii
grep -rliE 'CREATE[[:space:]]+TRIGGER' ScriptsFolder/Tables | wc -l   # 18 files
grep -rhoiE 'CREATE[[:space:]]+TRIGGER' ScriptsFolder/Tables | wc -l  # 54 triggers

# --- cross-DB refs: classify executable vs comment (this is the part §5.3 got wrong) ---
#   mask /* */ and -- regions, then match BOTH `db..obj` and bracketed 3-part forms.
#   See §3.3 for the resulting table.

# --- re-tag after any domains.json change, BEFORE map ---
cd $ROOT && "$LLS" tag-domains --repo-root legacy/<system> --domains analysis/<system>/domains.json

# --- coverage / ambiguity check against the index universe ---
#   iterate repo_files, match each path against domain path_globs then exclude_globs
#   with pathspec GitWildMatch; count files matching >1 domain (must be 0).
```
