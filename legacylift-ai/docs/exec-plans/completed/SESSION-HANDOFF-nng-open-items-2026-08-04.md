# Session Handoff — NNG refresh, open decisions (2026-08-04)

> ## ⚠ SUPERSEDED as of 2026-08-05 — all three items are CLOSED. Nothing here is actionable.
> Read this as a **historical record + reference**. Still useful: §1 (where everything is),
> §2 (environment traps), §6 (corrections already applied), §9 (memory pointers). Do **not**
> action §3, §4 or §5.
>
> | Item | This file said | Actually |
> |---|---|---|
> | §3 — A, restore a named security domain | "Ask the user; here is the procedure" | **Closed "no."** Measured: the app's Security Findings carry **0 of 63** citations inside the 11-file security package. `domains.json` unchanged → **no re-tag, no `map` re-run**. §3.1's file list was also **incomplete** — corrected in place |
> | §4 — B, credential rotation | "User action, external; assume all live" | **Closed, out of scope.** Review-only engagement: reported, not remediated. Findings **not** retracted; still assume all 15 live |
> | §5 — C, the `pleaud` question | "Give the user the query, record the answer" | **Closed as an external dependency.** Needs a live server; the three queries and the severity consequence now live in [plan §0-C](./refresh-nng-analysis.md#c--the-pleaud-question-closed-2026-08-05-external-dependency) |
>
> The parent plan is complete and sits beside this file:
> [`refresh-nng-analysis.md`](./refresh-nng-analysis.md). Both moved to `completed/` on
> 2026-08-05. **Do not re-run the pipeline** — the analysis outputs are gitignored and
> on-disk only, so a re-run destroys them rather than refreshing them.

**Original purpose (superseded):** work the three open items in
[`refresh-nng-analysis.md` §0](./refresh-nng-analysis.md#0-decisions--all-closed-2026-08-05).

**Do not re-run the pipeline.** `preflight` → `assess` → `tag-domains` → `map` completed on
both systems on 2026-08-04 and all artifacts validate. Re-running would overwrite good output.

---

## 1. Where everything is

Everything below is **untracked and on-disk only** — `repos/nng-app-legacylift-analysis/` is
gitignored at `.gitignore:92`. It is not recoverable if deleted, and `git status` stays clean
no matter what you write there.

| What | Path |
|---|---|
| The plan (open items in §0) | `docs/exec-plans/active/refresh-nng-analysis.md` |
| App analysis | `repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app/` |
| DB analysis | `repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.db.ETSPii/` |
| Prior runs (reference only — never write here) | `analysis-original/`, `analysis-domains-enhanced/`, `analysis-semantic-search-enhanced/` |

Per system: `PREFLIGHT.md`, `ASSESSMENT.md`, `domains.json`, `ARCHITECTURE.mmd`,
`topology.json`, `TOPOLOGY.html`, `extract_topology.py`, `call-graph.mmd`,
`data-lineage.mmd`, `critical-path.mmd`. The app additionally has `SECRETS.local.md`
(gitignored, all values masked). The DB has none — it contains **zero** credentials, an
explicit verified negative.

**Read the assessments rather than re-deriving anything.** Both were written this session
against a fresh index and carry inline `file:line` evidence.

---

## 2. Environment — read before running anything

Two traps cost real time this session. Both are recorded in memory
([[legacylift-knowledge-store-survives-reset]], [[legacylift-index-emits-no-dispatch-edges]]).

1. **`legacylift-search` on PATH is BROKEN** — `ModuleNotFoundError: legacylift_search`.
   Use the venv binaries:
   ```bash
   LLS=/c/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/legacylift-search.exe
   PY=/c/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe
   ```
   `$PY` is also the only interpreter here with `pathspec`.

2. **The knowledge store survives everything.** It lives at
   `legacy/<system>/legacylift-docs/knowledge/knowledge.sqlite` — outside the index dir,
   never cleared by `--reset`, and unaffected by clearing `analysis/`. **Any `domains.json`
   edit requires re-running `tag-domains`**, or `map` groups by stale IDs.

Minor, but they will bite: a bash heredoc mangles `'\\'` in embedded Python (use `chr(92)`);
`sqlite3.connect` *creates* a missing file, so use `file:...?mode=ro` for read probes;
`grep -P` is unsupported (use `sed -E`); Bash tool needs absolute `/c/Users/...` paths.

---

## 3. Item A — CLOSED 2026-08-05, decided "no"

**Do not execute this section.** The user decided not to restore a named security domain in
either system. `domains.json`, `file_domains` tagging, `ARCHITECTURE.mmd` and `topology.json`
are all unchanged and final. Decisive evidence: the app's Security Findings section carries 63
citations across 53 files and **0** of them land in the 11-file security package, because the
findings cite enforcement sites in the business domains, not the security plumbing. Full
argument in [plan §0-A](./refresh-nng-analysis.md#a--the-security-domain-question-closed-2026-08-05).

The procedure below is retained as the record of *how* it would be done, if that judgement is
ever revisited on new evidence. It is a `domains.json` edit — **not** a re-run of assess.

### 3.1 Which files would move (corrected 2026-08-05)

Enumerated against the index universe (`repo_files`) with `pathspec` GitWildMatch, not an
on-disk walk — 11 app files and 28 DB files, both counts exact.

```bash
# app — 11 files, 1,092 LOC. NOTE: these leave TWO different domains, not just shared/core.
#   from shared-core-platform (9):
ple-persistence/JavaSource/com/nng/ple/persistence/security/**        # IdentityRetriever, SecurityRoles, SpringSecurityIdentityRetriever
ple-persistence/JavaSource/com/nngco/security/providers/**            # HazelcastConfiguration, HazelcastPleCacheMap
ple-services/JavaSource/com/nng/ple/service/security/PleSecurityManager.java
ple-services/JavaSource/com/nng/ple/service/util/SecurityAdvice.java
ple-web/src/main/java/com/nng/ple/web/tags/NngAuthorizeTag.java       # authz taglib
ple-web/src/main/java/com/nng/ple/web/FlagExpiredSessionFilter.java
#   from external-system-integration (2) — MISSING from the 2026-08-04 version of this list:
ple-model/JavaSource/com/nng/ple/model/external/NngUser.java
ple-model/JavaSource/com/nng/ple/model/external/SecUser.java

# DB — 28 files, 223 LOC, all in shared-core-platform-reference. FILES, not tables: zero
# tables are involved. 23 role scripts + 5 schema scripts; 13 are 3-line bare CREATE ROLE
# stubs with no grants; only 5 files carry any grant at all.
ScriptsFolder/Security/Roles/*      # 23
ScriptsFolder/Security/Schemas/*    #  5
```

**The `external-system-integration` pair is the trap.** Carving only the shared/core paths
listed in the 2026-08-04 version of this section would leave `NngUser.java` and `SecUser.java`
matching two domains — reintroducing exactly the ambiguity re-derivation eliminated, and
failing the §3.3 gate.

### 3.2 Steps

1. Add the domain to `analysis/<system>/domains.json` **and** remove the same paths from the
   shared/core `path_globs`. A file matching two domains is the failure mode re-derivation
   just eliminated — see §3.3.
2. Add the matching row to the **Architecture-at-a-Glance** table in that system's
   `ASSESSMENT.md`. The two must list an identical domain set; a mismatch forks the domain
   set across the pipeline.
3. Re-render the diagram (do **not** hand-author it):
   ```bash
   "$LLS" render-architecture --domains "analysis/<system>/domains.json" \
                              --output  "analysis/<system>/ARCHITECTURE.mmd"
   ```
4. Re-tag, then re-run map for that system only:
   ```bash
   "$LLS" tag-domains --repo-root "legacy/<system>" --domains "analysis/<system>/domains.json"
   "$PY" "analysis/<system>/extract_topology.py" --repo-root "legacy/<system>" \
        --domains "analysis/<system>/domains.json" --out "analysis/<system>/topology.json" \
        --system "<same display name as before>"
   ```
   then re-render `TOPOLOGY.html` with the injection-escaping snippet in
   `/modernize-map` (the `<` replacement is a real XSS guard — keep it).

### 3.3 Acceptance gate — the change is wrong unless this passes

Coverage must stay **100%** and ambiguity must stay **0**, measured against the *index*
universe (`repo_files`), not an on-disk walk. Method: iterate `repo_files`, match each path
against each domain's `path_globs` then `exclude_globs` using `pathspec` GitWildMatch, and
count files matching more than one domain. Baseline to preserve:

| | app | DB |
|---|---:|---:|
| assigned / excluded / unassigned | 846 / 383 / 0 | 565 / 3 / 0 |
| ambiguous | 0 | 0 |

`tag-domains` echoes its own counts and lists dropped domains — a useful independent check.

---

## 4. Item B — credential rotation (CLOSED 2026-08-05, out of scope)

**Not our action. Do not track it, do not chase it, do not re-open it as an open item.**
Review-only engagement: we report, the owner remediates. In a real engagement this would be
the first remediation item and we would drive it.

**The findings stand.** Closing B is a scope statement, not a retraction — the 15 credentials
are real, none is confirmed rotated, and **all should be assumed live**. Inventory, masked,
with rotation order for the owner's benefit:
`analysis/customer.ple.nng.app/SECRETS.local.md`.

Standing rules that still apply to any agent touching this material:

- **Never reproduce a credential value** — not in chat, not in a doc, not in a commit. The
  inventory is masked and `SECRETS.local.md` is gitignored; keep both true.
- Keep `--show-secrets` **off** for `/modernize-harden` unless the user explicitly asks.
- Nothing was ever gated on rotation, so nothing unblocks by closing it.

The two facts to lead with if this is ever handed to NNG: a committed PKCS#12 **private key**
reused across both applications *and* configured as the truststore, and one Hazelcast group
password byte-identical across dev/QA/model-office/**prod**, so a compromise in any lower
environment is a production compromise.

---

## 5. Item C — the `pleaud` permission question (CLOSED 2026-08-05, external dependency)

**Superseded.** The authoritative version — three queries (the per-database flag alone is not
sufficient; the server-level `cross db ownership chaining` option overrides it), the severity
consequence, and the two adjacent DBA asks — now lives in
[plan §0-C](./refresh-nng-analysis.md#c--the-pleaud-question-closed-2026-08-05-external-dependency).

The one rule that outlives the item: it is **not answerable from this repository**. Do not try
to infer it from the export, and do not let a subagent guess. If the answer ever arrives and
it is "chaining off, roles hold `INSERT` directly", the caller-supplied-audit-actor finding
(**121 of 337 procs**) escalates from High to effectively **Critical** — the trail becomes
forgeable — and the DB `ASSESSMENT.md` CWE-284 row should be updated then.

---

## 6. Corrections already applied — do not "re-discover" these

The 2026-08-03 version of the plan had five factual errors, all now corrected in place with
verified numbers ([plan §3](./refresh-nng-analysis.md#3--corrections-to-this-documents-own-earlier-findings)).
Summarised only so a fresh agent does not resurrect the old figures:

- DB triggers are **18 tables / 54 triggers / 72 audit inserts**, not 16/16.
- The two "broken cross-DB references" are **comment-only** — not bugs, and explicitly **not**
  an `extract-rules` task.
- `edsintfc` has **zero** executable references; a 6th DB (`dba`) exists; `etssec` uses
  3-part naming, so a parser tuned only for `db..obj` misses it.
- Prior-run metrics were **not** inflated (the *module* table in `PREFLIGHT.md` was; the
  `scc` table was fine).
- The §6 security list was materially incomplete.

---

## 7. If the engagement is ever extended beyond review-only

Out of scope for this plan, but the natural next commands, in priority order:

- **App → `/modernize-harden`.** Formalizes 23 security findings into a reviewable patch.
  Expect a Claude-derived review, not tool-corroborated: no SAST binary is installed and
  there are zero jars in the tree, so no dependency-CVE scan is possible until the build
  resolves.
- **DB → `/modernize-extract-rules`.** Higher value than harden for this system: 337 procs
  and 51 views all parse clean and are where the business logic lives. Scoping note: do
  **not** ask it to adjudicate the misspelled references (see §6).
- **Either → `/modernize-uplift`**, but only after the app's build is restored and its
  persistence layer is off the removed Hibernate 3 APIs. A delta catalog authored now would
  be unverifiable, since a dual-run is blocked while the build is broken.

---

## 8. Suggested skills

| Skill | When |
|---|---|
| ~~**`code-modernization:modernize-map`**~~ | **Not needed.** Its only trigger was Item A, now closed "no" — `domains.json` is unchanged, so the existing `topology.json` / `TOPOLOGY.html` stay valid. Do not re-run. |
| **`code-modernization:modernize-status`** | Cheap orientation at session start — artifact inventory, staleness, secrets hygiene, next step. Good first call to confirm nothing drifted since 2026-08-04. |
| **`code-modernization:modernize-harden`** | Only if the user extends scope (§7). Reads `SECRETS.local.md`; keep `--show-secrets` **off** unless the user explicitly asks. |
| **`code-modernization:modernize-extract-rules`** | Only if the user extends scope (§7), DB first. |

Do **not** invoke `modernize-assess` — it would overwrite validated `ASSESSMENT.md`,
`domains.json` and `ARCHITECTURE.mmd` for both systems.

**Subagents:** this session used the six-agent sweep only because `/modernize-assess` Step 3
mandates it. The one remaining open item needs no subagents — it is a question for the
client/DBA. Two agents also disagreed with each other on the DB trigger count and **both were
wrong** — verify contested numbers directly rather than accepting an agent's figure. Item A
was likewise settled by direct measurement (`pathspec` against `repo_files`, then a citation
overlap test on each `ASSESSMENT.md`), not by an agent's judgement.

---

## 9. Memory pointers

Written or updated this session; recall them rather than re-deriving:

- `legacylift-knowledge-store-survives-reset` — clearing `analysis/` does not clear domain
  tagging; PATH shim broken; `tag-domains` before `map`.
- `legacylift-index-emits-no-dispatch-edges` — the index binds at 0.7/0.85 or not at all, so
  `map` dispatch edges come from framework config; T-SQL `uses_table` reports aliases as
  datastores.
- `sql-extractor-ssms-shape` — updated with the `CREATE  trigger` double-space trap.
- `domain-set-canonical-flow`, `domain-excluded-by-design-tier` — still accurate.
