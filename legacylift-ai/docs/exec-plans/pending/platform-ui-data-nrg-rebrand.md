# Rebrand the platform-ui demo data from the NNG engagement to a generic NRG

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository has no `PLANS.md`; the ExecPlan format is defined in
[`docs/exec-plan.md`](../../exec-plan.md), and this document must be maintained in accordance
with it.

## Purpose / Big Picture

`platform-ui` is LegacyLift v4's read-only review surface — a .NET 10 minimal API plus an
Angular 21 front end — and it ships with a **copy** of one real engagement's analysis output in
`platform-ui/data/` so the UI has something to render when you start it. That engagement was for
Northern Natural Gas, and the copy was saturated with the client's identity: the token `NNG`
appeared 20,648 times, the spelled-out company name appeared in assessment prose and in generated
requirement text, one database name carried an employee's first name, and the two system
directories were themselves named after the client (`customer.ple.nng.app`,
`customer.ple.nng.db.ETSPii`).

After this change, someone can start `platform-ui` and demo it to anyone — another client, a
conference, a recorded walkthrough — without exposing who the engagement was for. Concretely:
`curl http://localhost:5199/api/projects` reports a project named `NRG — Pipeline Location Engine`
with systems `customer.ple.nrg.app` and `customer.ple.nrg.db.Core`; searching the requirements
store for `nng` returns zero rows and for `nrg` returns 22; and `grep -ri nng platform-ui/data`
finds nothing.

The change is confined to `platform-ui/data/`. **No client source code is touched, and the
upstream analysis corpora under `repos/nng-app-legacylift-analysis/` are deliberately left
alone** — see the Decision Log for why.

This work has already been performed once, on 2026-09-15, against the working copy on Darrell
Norton's machine. **The reason this plan exists is that `platform-ui/data/` is gitignored, so that
work is not in version control and cannot be recovered from git.** Anyone who regenerates
`platform-ui/data/` — which is what `platform-ui/tools/prepare_data.py` does — gets the
NNG-branded content back and must redo the rebrand. This plan is the reproducible recipe, and it
has been validated by replaying it from a pristine NNG copy and diffing the result against the
rebranded folder (see `Validation and Acceptance`).

## Progress

- [x] (2026-09-15) Surveyed the blast radius: 20,648 `NNG`-token occurrences across 13 text
      files, 2 SQLite stores and 2 directory names; established that `platform-ui/data/` is
      gitignored and therefore has no git safety net.
- [x] (2026-09-15) Established that the API resolves each system's directory from the `systemId`
      in `platform-ui/data/projects.json`, so renaming directories needs no code change; confirmed
      nothing in `platform-ui/api/` or `platform-ui/web/src/` hardcodes a system id.
- [x] (2026-09-15) Pass 1 — `NNG`/`Nng`/`nng` → `NRG`/`Nrg`/`nrg`, plus the spelled-out client
      name, plus the two directory renames and `projects.json`.
- [x] (2026-09-15) Pass 2 — the `ETSPii` system name → the generic `Core`, and the employee's
      first name dropped from `Jim_Copy_ETSPII_For_CapTech`.
- [x] (2026-09-15) Pass 3 — the hyphenated `Northern-Natural-Gas-operated` that Pass 1 missed,
      and the client pipeline named by short name beside its two siblings.
- [x] (2026-09-15) Consolidated all three passes into one idempotent script, and validated it by
      replaying from a pristine NNG copy: all 15 text files byte-identical to the hand-rebranded
      folder, all logical SQLite tables identical, FTS5 search results identical.
- [x] (2026-09-15) Found and closed a de-identification hole the first three passes left: the old
      strings survived verbatim in the SQLite files' freed pages, recoverable with `strings` even
      though every query returned nothing. Added `VACUUM` to the script and ran it on both live
      stores; raw-file residue 544 and 110 → 0 and 0.
- [ ] Decide whether `platform-ui/tools/prepare_data.py` should emit NRG-branded output directly,
      which would make this plan unnecessary for future regenerations (completed: the problem is
      identified and the exact constants are named in `Interfaces and Dependencies`; remaining:
      the change itself, which is a decision for the plan's owner because it hardcodes a
      rebranding into a tool whose purpose is faithful copying).
- [ ] Decide whether the upstream corpora under `repos/nng-app-legacylift-analysis/analysis*/`
      should be rebranded too (see the Decision Log entry declining to do so unasked).

## Surprises & Discoveries

- Observation: `platform-ui/data/` is **entirely untracked**, so there is no `git checkout` to
  undo a bad pass. Every destructive step needs an out-of-band backup first.
  Evidence: `git ls-files platform-ui/data` returns nothing at all.

- Observation: the API is **fully data-driven** off `projects.json`. `Catalog.cs:37` builds each
  store path as `Path.Combine(dataRoot, id, "knowledge.sqlite")` where `id` is the `systemId`
  string, and `Catalog.cs:58` does the same for the system directory. Renaming a directory and its
  `systemId` together therefore needs no recompilation, and a stale id 404s cleanly.
  Evidence: after the rename, `GET /api/systems/customer.ple.nrg.db.Core` returns 200 and
  `GET /api/systems/customer.ple.nrg.db.ETSPii` returns 404, with no code edited.

- Observation: the bulk of the `nng` count is not branding at all — it is **Java package paths**.
  17,817 of the 20,648 hits are in one file, `customer.ple.nng.app/TOPOLOGY.html`, as graph node
  labels like `ple-services/JavaSource/com/nng/ple/service/point/validator/...`.
  Evidence: a per-file count put `TOPOLOGY.html` at 17,817 and the next largest file,
  `docs/BUSINESS_RULES.md`, at 1,052.

- Observation: `gr_fts` is a **regular FTS5 table with no synchronising triggers** — the
  application populates it by hand. So updating the `gr` base table alone leaves the search index
  stale, and patching the `gr_fts_content` shadow table directly corrupts it. The correct move is
  `UPDATE gr_fts SET ... WHERE rowid = ?`, which makes FTS5 maintain its own index.
  Evidence: `select sql from sqlite_master where name like 'gr_fts%'` shows
  `CREATE VIRTUAL TABLE gr_fts USING fts5(gr_id UNINDEXED, name, statement, as_built, rationale)`
  and five `gr_fts_*` shadow tables, and `select name,type from sqlite_master where type='trigger'`
  returns no rows.

- Observation: **`fts5(... 'rebuild')` is not available here.** That command only works on an
  external-content FTS5 table. `gr_fts` stores its own content in `gr_fts_content`, so the index
  must be maintained through ordinary `UPDATE`s rather than rebuilt after the fact.
  Evidence: `gr_fts_content` holds 379 rows, one per `gr` row, which is what a non-external-content
  FTS5 table looks like.

- Observation: **a case-sensitive `replace()` behind a case-insensitive `LIKE` filter silently
  does nothing.** SQLite's `LIKE` is case-insensitive for ASCII but its `replace()` is not, so
  `UPDATE ... SET col = replace(col,'Northern Natural Gas','NRG') WHERE col LIKE '%northern
  natural gas%'` matches rows and then leaves them untouched. Worse, a verification query written
  with the same case-sensitive literal reports success.
  Evidence: Pass 1 reported zero residual `Northern Natural`, yet
  `Northern-Natural-Gas-operated` was still present in `gr.sme_question` — the hyphens, not the
  case, defeated it, and the verification used the same space-separated literal so it agreed.
  This is why the consolidated script matches with `Northern[\s\-]+Natural` under `re.I` and
  verifies with a **deliberately looser** pattern than it substitutes.

- Observation: a naive `ETS` rename would be **destructive**, which is why only the full `ETSPii`
  system name was changed. Case-sensitive `ETS` occurs inside `SECRETS` (7 times). Lowercase `ets`
  occurs inside `sets` (28), `resets` (17), `targets` (13), `assets` (11), `gets` (10),
  `meetsOverrideCriteria` (6), `datasets`, `lets` and `interprets` — 128 hits of pure collateral.
  Evidence: an identifier-scoped scan of `platform-ui/data` counted 477 hits across 38 distinct
  `ETS*`-family identifiers against 128 hits in unrelated English words.

- Observation: the `ETS*` identifiers are **schema object names, not client branding** —
  `ETSCompany` (71 hits), `EtsstateType` (59), `Etscounty` (53), `REPLIC_ETSCompany`,
  `FK_ETSCompany_LegalEntity`, `up_insertETSCompany`, `Etscompany.hbm.xml`, `EtscountyDao.java`.
  Renaming them would make the documentation cite tables, views, foreign keys, Java classes and
  Hibernate mappings that do not exist in the source it points at.
  Evidence: 422 `ETS*`/`SECRETS` identifier hits remain after the rebrand, by design, and
  `GET /api/systems/customer.ple.nrg.db.Core/domains` still names `ETSCompany`, `ETSCounty` and
  `ETSState`.

- Observation: three occurrences of `NORTHERN` are **sample data in Given/When/Then scenarios**,
  not the client, and one of them **asserts its own length**. The scenario reads "Given a legal
  entity long name of NORTHERN STATES POWER COMPANY OF MINNESOTA INCORPORATED (54 characters)".
  Renaming it would falsify the assertion the scenario exists to pin down.
  Evidence: 14 hits of `NORTHERN UTILITIES` / `NORTHERN STATES POWER` survive the rebrand on
  purpose, guarded by the `KEEP` pattern in the script.

- Observation: reading a Windows CRLF file with Python's default universal-newline translation and
  writing it back in text mode **rewrites every line ending in the file** as a side effect. The
  first consolidated draft did this and produced a 2,697-byte `projects.json` where the
  hand-rebranded one was 2,801 bytes — 104 lines, 104 lost carriage returns — despite identical
  content.
  Evidence: `cmp` reported a difference at char 2 of line 1, while
  `diff <(tr -d '\r' < a) <(tr -d '\r' < b)` reported the files identical. Fixed by using binary
  I/O throughout, which is what the original hand pass happened to do.

- Observation: **updating a SQLite row does not remove the old text from the file.** After all
  three passes every query returned zero residue, yet the raw `.sqlite` files still contained the
  client's name verbatim in pages the freelist had released: 509 `nng`, 28 `NNG` and 7 `Nng` in
  the app store, and 61 `ETSPii` plus 49 `nng` variants in the database store. For a folder whose
  whole purpose is to be shown to other people, that is the difference between "the UI does not
  display it" and "the file does not contain it" — anyone running `strings knowledge.sqlite`
  recovers the engagement. `VACUUM` rebuilds the file from live content only and closes it.
  Evidence: `grep -oac nng knowledge.sqlite` reported 544 hits with `pragma freelist_count` at 74
  of 1,089 pages; after `VACUUM`, 0 hits, freelist 0, 1,089 → 984 pages, with
  `pragma integrity_check` `ok`, FTS5 `integrity-check` passing, `gr` and `gr_fts` both still 379
  rows and `match 'nrg'` still 22.

- Observation: two FTS5 **internal** tables legitimately differ between two runs that produce
  identical search behaviour. `gr_fts_data` and `gr_fts_idx` hold B-tree segment blobs whose
  packing depends on the order rows were written, so replaying the rebrand in one pass rather than
  three yields 50 versus 49 segment rows. This is not a defect and must not be "fixed".
  Evidence: every logical table matched; only `gr_fts_data` and `gr_fts_idx` differed; and both
  copies returned identical counts for `match 'nrg'` (22), `'nng'` (0), `'northern'` (0),
  `'core'` (1) and `'etspii'` (0), with `integrity-check` passing on both.

## Decision Log

- Decision: rename the two system directories and their `systemId` values, not just file contents.
  Rationale: the ids appear in every API URL and in the UI's own system picker, so leaving them as
  `customer.ple.nng.*` would defeat the purpose while the prose was clean. The API derives the
  directory from the id, so the two move together and no code changes.
  Date/Author: 2026-09-15, Darrell Norton (decision), Claude (survey and execution).

- Decision: replace `ETSPii` with the generic `Core`, and leave the whole `ETS*` schema vocabulary
  intact.
  Rationale: `ETSPii` is the client's system name and is never a substring of another identifier,
  so replacing it is both worthwhile and safe. The `ETS*` table and class names are what the
  source actually calls those objects; renaming them would break the correspondence between the
  documentation and the code it cites, which is the thing the analysis is selling. Scoping to the
  full `ETSPii` token also sidesteps the `SECRETS`/`sets`/`targets` collateral entirely.
  Date/Author: 2026-09-15, Darrell Norton, from a measured comparison of the two scopes.

- Decision: use `Core` rather than `NRGPii` or `Pii`.
  Rationale: offered three options; `Core` was chosen as fully generic, dropping both the client
  acronym and the PII signal rather than advertising in the UI that this database holds cleartext
  personal data.
  Date/Author: 2026-09-15, Darrell Norton.

- Decision: drop the employee first name from `Jim_Copy_ETSPII_For_CapTech`, giving
  `Copy_CORE_For_CapTech`.
  Rationale: a person's first name is a personal identifier, and neither the NNG pass nor the
  ETSPii pass would have touched it. Raised as a separate question precisely because it is not an
  instance of either rename.
  Date/Author: 2026-09-15, Claude (found it), Darrell Norton (approved).

- Decision: also rename the bare `Northern` where it names the client pipeline beside its two
  siblings — "the legacy Northern, Transwestern and Florida Gas systems" becomes "the legacy NRG,
  Transwestern and Florida Gas systems".
  Rationale: it is the same company referred to by short name, so leaving it would leak the
  identity the rest of the pass removes. Recorded here rather than assumed silently because the
  literal request was to replace "Northern Natural Gas", and this is one step beyond that.
  Date/Author: 2026-09-15, Claude, reported to Darrell Norton at the time.

- Decision: do **not** rename `NORTHERN UTILITIES` or `NORTHERN STATES POWER COMPANY OF
  MINNESOTA`.
  Rationale: these are sample legal-entity values inside test scenarios, not the client's own
  identity, and one scenario asserts the character count of the Minnesota string. Renaming would
  turn a correct assertion into a false one.
  Date/Author: 2026-09-15, Claude, reported to Darrell Norton at the time.

- Decision: leave the upstream corpora under `repos/nng-app-legacylift-analysis/analysis*/`
  unmodified, including the five `ASSESSMENT.md` files there that still say "Northern Natural Gas".
  Rationale: two reasons. The scope given was `platform-ui/data` only; and `CLAUDE.md` records
  those `analysis*/` trees as generated output that the active ExecPlans describe as
  unreproducible, not to be deleted or overwritten. Rebranding them is a much larger job than
  rebranding the copy, and it would destroy the corpora the plans measure against.
  Date/Author: 2026-09-15, Claude (declined unasked), pending a decision from Darrell Norton.

- Decision: do the SQLite text substitution row-by-row in Python rather than with SQL `replace()`.
  Rationale: the client-name match needs to be case-insensitive and separator-flexible, which SQL
  `replace()` cannot express — and the mismatch between a case-insensitive `LIKE` filter and a
  case-sensitive `replace()` is exactly what caused the missed hyphenated form in Pass 1.
  Date/Author: 2026-09-15, Claude.

- Decision: `VACUUM` each store after rewriting it, and treat a raw-file `grep` — not a SQL query
  — as the acceptance check for the stores.
  Rationale: a rewritten row leaves its old text in freed pages, so a query-based check certifies
  a file that still carries the client's name to anyone who reads its bytes. Since the point of
  this rebrand is that the folder can be handed to third parties, the file contents are the thing
  that must be clean, and only `VACUUM` makes them so. The cost is a full rewrite of each store,
  which at 4 MB is negligible.
  Date/Author: 2026-09-15, Claude, after grepping the binaries during plan validation.

- Decision: verify with a looser pattern than the one used to substitute.
  Rationale: Pass 1's verification used the same literal as its substitution, so it could not
  detect a form the substitution did not cover, and it reported a clean result over live residue.
  The `RESIDUE` regex in the script is therefore deliberately broader than `SUBS`.
  Date/Author: 2026-09-15, Claude, after the miss was found.

## Outcomes & Retrospective

The rebrand is complete on the working copy as of 2026-09-15, and the consolidated script
reproduces it exactly from a pristine NNG copy. Final state: zero occurrences of `nng`, `etspii`,
`Jim_Copy`, `Northern Natural` (any separator or case), `Northern, Transwestern` or `National
Fuel` anywhere in `platform-ui/data/` — in the text files **and in the raw bytes of both SQLite
stores**, which is a stronger claim than the first three passes could make. Both stores pass
`PRAGMA integrity_check` with `freelist_count` 0; the app store's FTS5 index passes its own
`integrity-check` with `gr` and `gr_fts` both at 379 rows; and all 379 requirements, their 383
citations and their diagrams and topology render through the API.

What survives by design: 422 `ETS*`/`SECRETS` schema-identifier hits, and 14 `NORTHERN UTILITIES`
/ `NORTHERN STATES POWER` sample-data hits.

Three lessons worth carrying. First, **a verification pattern that mirrors the substitution
pattern is not a verification** — Pass 1 reported clean over live residue because both used the
same space-separated literal, and only a human reader noticing the name in a document surfaced it.
Verify with a looser net than you substitute with. Second, **for a de-identification job, query
the bytes rather than the data** — three passes and three green verifications all ran as SQL, and
all three missed 654 occurrences of the client's name sitting in freed database pages; one
`grep` over the raw files found them immediately. Third, **"replace X with Y everywhere" is almost
never the actual request** on a real corpus: of the six identifier families examined here, two
were client identity to remove, two were schema vocabulary to preserve, one was sample data
carrying a length assertion, and one was an employee's name nobody had asked about.

What remains is the two unchecked `Progress` items: whether `prepare_data.py` should emit
NRG-branded output directly, and whether the upstream corpora should be rebranded. Both are
decisions for the plan's owner, not omissions.

## Context and Orientation

Everything in this section is about files you can list and read in the current working tree.

**`platform-ui/`** is one of LegacyLift v4's three deployable components, described in
[`docs/architecture.md`](../../architecture.md). It has four parts:

`platform-ui/api/` is a .NET 10 minimal API. The two files that matter here are
`platform-ui/api/Program.cs`, which declares the HTTP routes, and
`platform-ui/api/Data/Catalog.cs`, which reads the data folder. `platform-ui/web/` is the Angular
21 front end. `platform-ui/tools/prepare_data.py` is the script that populates the data folder by
copying from an analysis workspace. And **`platform-ui/data/` is that data folder** — the subject
of this plan.

`platform-ui/data/` is **gitignored**, so it does not appear in `git status` and `git ls-files
platform-ui/data` returns nothing. Confirm this before you start: it means there is no version
control undo, and every step here takes a manual backup first.

The folder holds one file and two directories, one per analysed system:

    platform-ui/data/
      projects.json                       the catalog the API reads first
      customer.ple.nrg.app/               the Java application (after rebrand)
        knowledge.sqlite                  the requirements store, 379 requirements
        knowledge.sqlite-wal, -shm        SQLite write-ahead log and shared-memory files
        domains.json                      capability domains and their file globs
        snippets.json                     cited source excerpts, one per citation
        TOPOLOGY.html                     a large pre-rendered dependency graph
        diagrams/*.mmd                    four Mermaid diagrams
        docs/*.md                         ASSESSMENT, PREFLIGHT, BUSINESS_RULES, DATA_OBJECTS
      customer.ple.nrg.db.Core/           the SQL Server database (after rebrand)
        ... the same shape, without BUSINESS_RULES.md or DATA_OBJECTS.md

Before the rebrand those two directories were named `customer.ple.nng.app` and
`customer.ple.nng.db.ETSPii`.

**Why the directory names matter.** `projects.json` lists systems, each with a `systemId`. The API
treats that string as the directory name: `Catalog.cs:37` builds the store path as
`Path.Combine(dataRoot, id, "knowledge.sqlite")` and `Catalog.cs:58` exposes
`SystemDir(systemId) => Path.Combine(DataRoot, systemId)`. Nothing else maps ids to paths, and
nothing in `platform-ui/api/` or `platform-ui/web/src/` hardcodes a specific id. So a directory
and its `systemId` must be renamed **together**, and when they are, no code changes and no
rebuild is needed.

**Two terms used below.**

*SQLite WAL* — "write-ahead log". SQLite can journal changes into a sibling `-wal` file and only
later fold them into the main `.sqlite` file. That folding is called a *checkpoint*. If you write
to one of these stores and do not checkpoint, your changes live in the `-wal` file; copying only
the `.sqlite` file elsewhere would lose them. The script checkpoints with
`PRAGMA wal_checkpoint(TRUNCATE)` before and after its work so the `.sqlite` file is always the
whole truth.

*FTS5* — SQLite's full-text search extension. A "virtual table" declared with
`USING fts5(...)` looks like an ordinary table but keeps an inverted index in a set of companion
"shadow" tables, here `gr_fts_data`, `gr_fts_idx`, `gr_fts_content`, `gr_fts_docsize` and
`gr_fts_config`. In this store the searchable table is `gr_fts`, mirroring four columns of the
`gr` requirements table. It has **no triggers**, so nothing updates it automatically when `gr`
changes — the application writes both. Two consequences drive the script's design: you must update
`gr_fts` explicitly as well as `gr`, and you must do it through the `gr_fts` virtual table so FTS5
maintains its own index, never by writing `gr_fts_content` directly.

## Plan of Work

The work is one script run against one directory, plus a backup before and a verification after.

Copy the script from `Concrete Steps` below into a file — `platform-ui/tools/rebrand_data.py` is a
reasonable home, or anywhere outside `platform-ui/data/` if you would rather not add a file. It
takes the data directory as its argument and a `--check` flag that reports what it would change
without writing.

The script makes four kinds of change, in this order, and the order is load-bearing:

First it rewrites the **text files** — every `.md`, `.mmd`, `.json` and `.html` under the data
directory — using binary reads and writes so Windows CRLF line endings survive untouched.

Second it rewrites the **SQLite stores**, row by row in Python rather than with SQL `replace()`,
because the client-name match must be case-insensitive and tolerate hyphens where the text has
spaces. For each table it selects every column, substitutes in Python, and writes back only the
rows that changed. The `gr_fts` virtual table is handled like any other table except that its
`gr_id` column is skipped — that column is declared `UNINDEXED` in the FTS5 schema and must not be
reassigned. The five `gr_fts_*` shadow tables are skipped entirely, because FTS5 owns them.

Third it renames the **directories**, walking deepest-first so renaming a parent cannot invalidate
a child's path.

Within the substitutions, two orderings matter. `Jim_Copy_ETSPII_For_CapTech` must be replaced
before the generic `ETSPII` rule, or the employee's first name survives as `Jim_Copy_CORE_For_
CapTech`. And the spelled-out client names must be collapsed to `NRG` before the `NNG` token rule
runs, so `National Fuel Gas (NNG)` becomes `NRG` rather than the half-renamed `NRG (NRG)`.

Two guards protect against the failures documented in `Surprises & Discoveries`. The `KEEP`
pattern marks spans that must never be touched — `NORTHERN UTILITIES` and `northern states power`
— and no substitution is applied inside one. And the `RESIDUE` pattern, used to count occurrences
and to drive `--check`, is deliberately **broader** than the substitutions, so a form the
substitutions fail to cover shows up as residue instead of passing silently.

## Concrete Steps

All commands assume a Bash shell with the repository root as the working directory. On Windows,
Git Bash is what these were run in.

**Step 1 — confirm the data folder is untracked, so you know there is no git undo.**

    $ cd /c/Users/dnorton/captechdev/legacylift-ai
    $ git ls-files platform-ui/data | wc -l
    0

Zero means untracked, as expected. Take the backup in Step 2 seriously.

**Step 2 — back the folder up somewhere outside the repository.**

    $ cp -r platform-ui/data /tmp/data-backup-$(date +%Y%m%d-%H%M)
    $ du -sh /tmp/data-backup-*
    8.8M    /tmp/data-backup-20260915-1413

**Step 3 — write the script.** Save the following as `platform-ui/tools/rebrand_data.py`. It is
reproduced in full here because this plan must be self-contained.

    """Rebrand a platform-ui/data copy from the NNG engagement to the generic NRG.

    Run against a freshly generated platform-ui/data (the NNG-branded output of
    platform-ui/tools/prepare_data.py). Idempotent: a second run finds nothing and
    changes nothing.

    Usage:
        python rebrand_data.py <path-to-data-dir> [--check]

    --check reports what would change and exits non-zero if anything would, without
    writing. Use it to verify a redo landed.
    """
    import os, re, sqlite3, sys

    TEXT_EXT = (".md", ".mmd", ".json", ".html")

    # FTS5 keeps its index in these shadow tables. Writing them directly desyncs
    # search; the gr_fts virtual table is updated instead and maintains them.
    FTS_SHADOW = ("gr_fts_data", "gr_fts_idx", "gr_fts_content",
                  "gr_fts_docsize", "gr_fts_config")

    # Sample legal-entity names inside Given/When/Then scenarios -- NOT the client.
    # One scenario asserts the length of the Minnesota name ("54 characters"), so
    # renaming it would falsify the assertion the scenario exists to pin down.
    KEEP = re.compile(r'NORTHERN\s+UTILITIES|northern\s+states\s+power', re.I)

    # Ordered. Literal string pairs and compiled regexes may be mixed; the
    # Jim_ entry must precede the ETSPII rule or the first name survives.
    SUBS = [
        ("Jim_Copy_ETSPII_For_CapTech", "Copy_CORE_For_CapTech"),
        # The client name, any separator run (space, hyphen, newline), any case.
        # The hyphenated "Northern-Natural-Gas-operated" is why this is a regex.
        (re.compile(r'Northern[\s\-]+Natural(?:[\s\-]+Gas)?', re.I), "NRG"),
        # The client pipeline named by short name beside its two siblings:
        # "the legacy Northern, Transwestern and Florida Gas systems".
        (re.compile(r'\bNorthern\b(?=\s*,\s*Transwestern)'), "NRG"),
        # projects.json carried this placeholder; the real client is Northern
        # Natural Gas, handled above.
        ("National Fuel Gas (NNG)", "NRG"),
        ("National Fuel Gas", "NRG"),
        # The ETSPii system name -> generic Core. Never a substring of another
        # identifier, so plain string replacement is safe here.
        ("ETSPII", "CORE"),
        ("ETSPii", "Core"),
        ("Etspii", "Core"),
        ("etsPii", "core"),
        ("etspii", "core"),
        # The NNG token itself, case-preserving.
        ("NNG", "NRG"),
        ("Nng", "Nrg"),
        ("nng", "nrg"),
    ]

    # Anything still matching this after a run is residue. Deliberately looser than
    # SUBS so a form SUBS does not cover still shows up rather than passing silent.
    RESIDUE = re.compile(
        r'nng|etspii|Jim_Copy|Northern[\s\-]+Natural|'
        r'\bNorthern\b\s*,\s*Transwestern|National\s+Fuel', re.I)


    def sub(s):
        """Apply SUBS in order, never inside a KEEP span."""
        if not isinstance(s, str):
            return s
        for pat, rep in SUBS:
            keep = [(m.start(), m.end()) for m in KEEP.finditer(s)]
            rx = pat if hasattr(pat, "finditer") else re.compile(re.escape(pat))
            out, last = [], 0
            for m in rx.finditer(s):
                if any(m.start() < ke and m.end() > ks for ks, ke in keep):
                    continue
                out.append(s[last:m.start()])
                out.append(rep)
                last = m.end()
            out.append(s[last:])
            s = "".join(out)
        return s


    def walk_text(data):
        for dp, _, fn in os.walk(data):
            for f in fn:
                if f.endswith(TEXT_EXT):
                    yield os.path.join(dp, f)


    def walk_dbs(data):
        for dp, _, fn in os.walk(data):
            for f in fn:
                if f.endswith(".sqlite"):
                    yield os.path.join(dp, f)


    def do_text(data, check):
        n_files = n_occ = 0
        for p in walk_text(data):
            # Binary I/O throughout: these files are CRLF on Windows, and a
            # universal-newline read plus a text-mode write would silently rewrite
            # every line ending in the file as a side effect of the rebrand.
            raw = open(p, "rb").read()
            old = raw.decode("utf-8")
            hits = len(RESIDUE.findall(old))
            if not hits:
                continue
            new = sub(old)
            if new == old:
                continue
            n_files += 1
            n_occ += hits
            print(f"  {os.path.relpath(p, data)}: {hits} occurrences")
            if not check:
                open(p, "wb").write(new.encode("utf-8"))
        print(f"  {n_files} file(s), {n_occ} occurrences")
        return n_occ


    def do_db(path, data, check):
        print(f"  {os.path.relpath(path, data)}")
        c = sqlite3.connect(path)
        if not check:
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        tables = [r[0] for r in c.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%'")]
        total = 0
        for t in tables:
            if t in FTS_SHADOW:
                continue
            cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
            if not cols:
                continue
            # gr_id is UNINDEXED in the fts5 declaration and must not be reassigned.
            body = [x for x in cols if not (t == "gr_fts" and x == "gr_id")]
            quoted = ", ".join(f'"{x}"' for x in body)
            n = 0
            for rid, *vals in c.execute(
                    f'select rowid, {quoted} from "{t}"').fetchall():
                new = [sub(v) for v in vals]
                if new != vals:
                    n += 1
                    if not check:
                        c.execute(
                            f'update "{t}" set '
                            + ", ".join(f'"{x}"=?' for x in body)
                            + " where rowid=?", (*new, rid))
            if n:
                print(f"    {t}: {n} rows")
                total += n
        if not total:
            print("    (no matches)")
        if check:
            c.rollback()
        else:
            c.commit()
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            # VACUUM rebuilds the file from live content only. Without it the old
            # strings survive verbatim in freed pages: queries return nothing but
            # `strings knowledge.sqlite` still recovers the client name.
            c.execute("VACUUM")
        c.close()
        return total


    def main():
        if len(sys.argv) < 2:
            sys.exit(__doc__)
        data = os.path.abspath(sys.argv[1])
        check = "--check" in sys.argv
        if not os.path.isdir(data):
            sys.exit(f"not a directory: {data}")
        print(f"{'CHECK' if check else 'REBRAND'} {data}\n")

        print("== text files ==")
        changed = do_text(data, check)

        print("\n== sqlite stores ==")
        for p in walk_dbs(data):
            changed += do_db(p, data, check)

        print("\n== directories ==")
        renames = 0
        # Deepest first, so renaming a parent cannot invalidate a child's path.
        for dp, dn, _ in sorted(os.walk(data), key=lambda x: -x[0].count(os.sep)):
            for d in dn:
                if sub(d) != d:
                    renames += 1
                    print(f"  {d} -> {sub(d)}")
                    if not check:
                        os.rename(os.path.join(dp, d), os.path.join(dp, sub(d)))
        if not renames:
            print("  (none)")
        changed += renames

        if check:
            print(f"\nWOULD CHANGE: {changed}")
            sys.exit(1 if changed else 0)
        print(f"\nCHANGED: {changed}")


    main()

**Step 4 — dry-run it.** Nothing is written, and the exit status is 1 when there is work to do.

    $ python platform-ui/tools/rebrand_data.py platform-ui/data --check
    CHECK C:\Users\dnorton\captechdev\legacylift-ai\platform-ui\data

    == text files ==
      projects.json: 7 occurrences
      customer.ple.nng.app\domains.json: 291 occurrences
      customer.ple.nng.app\snippets.json: 383 occurrences
      customer.ple.nng.app\TOPOLOGY.html: 17818 occurrences
      ...
      15 file(s), 20695 occurrences
    ...
    WOULD CHANGE: 23597

**Step 5 — run it for real.**

    $ python platform-ui/tools/rebrand_data.py platform-ui/data

Expect this shape of output. The exact per-table row counts are the acceptance numbers for a
corpus matching the 2026-09-15 one; a regenerated corpus may differ if the analysis was re-run.

    == text files ==
      15 file(s), 20695 occurrences

    == sqlite stores ==
      customer.ple.nng.app\knowledge.sqlite
        domains: 12 rows
        domain_edges: 1 rows
        file_domains: 1504 rows
        gr: 377 rows
        gr_citation: 378 rows
        gr_scenario: 18 rows
        gr_edge_case: 6 rows
        gr_run: 3 rows
        gr_fts: 22 rows
      customer.ple.nng.db.ETSPii\knowledge.sqlite
        domains: 11 rows
        file_domains: 568 rows

    == directories ==
      customer.ple.nng.app -> customer.ple.nrg.app
      customer.ple.nng.db.ETSPii -> customer.ple.nrg.db.Core

    CHANGED: 23597

**Step 6 — confirm idempotence.** Run `--check` again. It must find nothing and exit 0.

    $ python platform-ui/tools/rebrand_data.py platform-ui/data --check
    ...
    WOULD CHANGE: 0
    $ echo $?
    0

## Validation and Acceptance

Four checks. The first three are mechanical; the fourth is the one that proves the UI still works.

**1. No residue — and grep the files, not the database.** This must print nothing at all. Note
that it deliberately has no `--include` filter: it reads the `.sqlite` files as binary too,
because a SQL query cannot see the old text left behind in freed pages. If this finds a
`.sqlite` file, the `VACUUM` in the script did not run.

    $ grep -ril "nng\|etspii\|jim_copy\|national fuel\|northern[ -]*natural" platform-ui/data

For the separator-flexible client-name forms that a plain `grep` cannot express, `--check` from
Step 6 reporting `WOULD CHANGE: 0` is the check — its `RESIDUE` pattern covers
`Northern[\s\-]+Natural` and `Northern, Transwestern` under case-insensitive matching, in both the
text files and every SQLite text column.

**2. The preserved vocabulary is still there.** These counts must be non-zero, or the pass was too
aggressive and you should restore from the Step 2 backup.

    $ grep -roh "ETSCompany\|ETSCounty\|ETSState\|Etscompany\|Etscounty\|Etsstate\|SECRETS" \
        platform-ui/data --include=*.md --include=*.json --include=*.html --include=*.mmd | wc -l
    422

All seven alternatives matter: the mixed-case `Etscompany`, `Etscounty` and `Etsstate` are the
Java class and Hibernate mapping names, and dropping them from the pattern undercounts to 199.

    $ python -c "
    import sqlite3,re
    c=sqlite3.connect('platform-ui/data/customer.ple.nrg.app/knowledge.sqlite')
    n=sum(len(re.findall(r'NORTHERN\s+UTILITIES|northern\s+states\s+power',v,re.I))
          for (v,) in c.execute('select given from gr_scenario') if v)
    print('sample-data hits kept in gr_scenario.given:',n)"
    sample-data hits kept in gr_scenario.given: 4

Across every text column of that store the same two names account for 14 hits. Both numbers are
correct; they differ because the names recur in `gr.extractor_payload` and `gr_scenario.then` as
well as in `given`.

A bare `grep -oai northern` on the app store still returns 15 hits after a correct run. Those are
the `NORTHERN UTILITIES` and `northern states power` sample values the `KEEP` pattern protects,
and they are expected; that is why check 1 matches `northern[ -]*natural` rather than `northern`
alone.

**3. The stores are intact and the search index is consistent.** Both stores must report `ok`, and
the app store's FTS5 `integrity-check` must not raise. `freelist_count` must be 0, which is how
you confirm the `VACUUM` ran.

    $ python -c "
    import sqlite3
    for p in ['platform-ui/data/customer.ple.nrg.app/knowledge.sqlite',
              'platform-ui/data/customer.ple.nrg.db.Core/knowledge.sqlite']:
        c=sqlite3.connect(p)
        print(p, c.execute('pragma integrity_check').fetchone()[0])
        try:
            c.execute(\"insert into gr_fts(gr_fts) values('integrity-check')\")
            print('  fts5 ok; gr=%d gr_fts=%d' % (
                c.execute('select count(*) from gr').fetchone()[0],
                c.execute('select count(*) from gr_fts').fetchone()[0]))
        except sqlite3.OperationalError:
            print('  no gr_fts (expected for the db unit)')
        c.rollback(); c.close()"
    platform-ui/data/customer.ple.nrg.app/knowledge.sqlite ok
      fts5 ok; gr=379 gr_fts=379
    platform-ui/data/customer.ple.nrg.db.Core/knowledge.sqlite ok
      no gr_fts (expected for the db unit)

**4. The API serves it end to end.** Start the API and exercise one endpoint of each kind. Nothing
is rebuilt and no configuration changes.

    $ cd platform-ui/api && dotnet run --urls http://localhost:5199

In another shell:

    $ B=http://localhost:5199; A=customer.ple.nrg.app; D=customer.ple.nrg.db.Core
    $ curl -s $B/api/projects | head -c 120
    {"projects":[{"projectId":"nrg","name":"NRG \u2014 Pipeline Location Engine","client":"NRG",...

    $ curl -s $B/api/systems/$D | head -c 80
    {"systemId":"customer.ple.nrg.db.Core","label":"Core Database","kind":"database",...

    $ curl -s "$B/api/systems/$A/stats" | head -c 40
    {"total":379,"byState":{"draft":379},...

    $ curl -s "$B/api/systems/$A/requirements?search=nng&pageSize=1" | head -c 30
    {"hasRequirements":true,"total":0,

    $ curl -s "$B/api/systems/$A/requirements?search=nrg&pageSize=1" | head -c 32
    {"hasRequirements":true,"total":22,

    $ curl -s "$B/api/systems/$A/requirements?search=northern&pageSize=1" | head -c 30
    {"hasRequirements":true,"total":0,

    $ curl -s -o /dev/null -w "%{http_code} %{size_download}\n" "$B/api/systems/$A/topology"
    200 2099558

    $ curl -s -o /dev/null -w "%{http_code} %{size_download}\n" "$B/api/systems/$D/topology"
    200 393590

    $ curl -s -o /dev/null -w "%{http_code}\n" $B/api/systems/customer.ple.nng.app
    404

Acceptance is all of: `search=nng` and `search=northern` return `"total":0`; `search=nrg` returns
`"total":22`; `stats` returns `"total":379`; `/topology` and `/diagrams/data-lineage.mmd` return
200 with non-zero bodies for both systems; the old `customer.ple.nng.app` id returns 404; and
`/api/systems/customer.ple.nrg.db.Core/domains` still mentions `ETSCompany`.

**Proving a replay is faithful.** If you want to confirm a fresh run reproduces a known-good
rebrand, diff the two. Every text file must be byte-identical:

    $ cd <replayed-copy> && for f in $(find . -type f \
        \( -name "*.md" -o -name "*.mmd" -o -name "*.json" -o -name "*.html" \)); do
        cmp -s "$f" "<known-good>/$f" || echo "DIFFERS: $f"; done
    (no output)

Every **logical** SQLite table must match too, but `gr_fts_data` and `gr_fts_idx` will differ and
that is correct — they hold FTS5's internal B-tree segments, whose packing depends on write order,
so one consolidated pass yields 50 segment rows where three sequential passes yielded 49. The
check that matters is that search behaves identically: `match 'nrg'` returns 22, `'nng'` 0,
`'northern'` 0, `'core'` 1 and `'etspii'` 0 in both copies, with `integrity-check` passing.

## Idempotence and Recovery

The script is safe to run repeatedly. Every substitution maps a token that must disappear onto one
that contains no match for any rule, so a second run finds nothing: `--check` exits 0 and reports
`WOULD CHANGE: 0`. The directory rename is likewise a no-op once applied, because the renamed
directory no longer matches.

It is also safe to run on a **partly** rebranded folder — one where, say, the text files were done
but the stores were not. Each file, each row and each directory is evaluated independently against
the current content, so the script converges regardless of where a previous run stopped.

The one step that is not recoverable from within the repository is the folder itself:
`platform-ui/data/` is gitignored, so **Step 2's backup is the only rollback**. To roll back,
delete the folder and restore the copy:

    $ rm -rf platform-ui/data && cp -r /tmp/data-backup-20260915-1413 platform-ui/data

If the API is running while you rebrand, stop it first. It opens the stores read-only, but a live
connection can hold a WAL that interferes with the checkpoint, and the catalog is read once at
startup so a running instance would serve stale ids anyway.

Failing that, the folder can always be regenerated with `platform-ui/tools/prepare_data.py` — see
the next section — and the rebrand re-applied.

## Artifacts and Notes

The full survey, for anyone deciding whether a future scope change is worth it. Counts are
occurrences in `platform-ui/data/` as of 2026-09-15, before the rebrand.

The `NNG` token, 20,648 occurrences: `nng` 19,890, `NNG` 455, `Nng` 303. By file, the top five
were `customer.ple.nng.app/TOPOLOGY.html` 17,818, `docs/BUSINESS_RULES.md` 1,052,
`snippets.json` 383, `domains.json` 291 and `docs/DATA_OBJECTS.md` 118. Most of it is Java package
paths of the form `com/nng/ple/...` rather than prose.

The `ETSPii` system name, 39 occurrences in nine text files plus 580 SQLite rows — of which 579
are just the `assess_run_id` string `2026-08-04T00:00:00Z-customer.ple.nng.db.ETSPii` repeated
across `domains` and `file_domains`. Lowercase variants: `etspii_fg` (a filegroup),
`Comm_etspii_PLEODS` (a replication publication), `etspii..object`.

The `ETS*` family that was **not** renamed, 477 hits across 38 distinct identifiers:
`ETSCompany` 71, `EtsstateType` 59, `Etscounty` 53, `Etscompany` 40, `ETSState` 26, `ETSCounty`
23, `EtsStateControlType` 18, `Etsstate` 13, `EtscountyDao` 12, and a long tail including
`REPLIC_ETSCompany`, `FK_ETSCompany_LegalEntity`, `up_insertETSCompany`, `etssec.dbo.SecUserSA`
and `etscontracts.LegalEntityArchive`. Against that, 128 hits where `ets` is an innocent substring
of an English word: `sets` 28, `resets` 17, `targets` 13, `assets` 11, `gets` 10,
`meetsOverrideCriteria` 6, plus `datasets`, `lets`, `interprets` — and `SECRETS` 7 for the
uppercase form. This is the measurement behind the decision to scope to the full `ETSPii` token
only.

The client name in prose, before the rebrand: `Northern Natural Gas` in
`customer.ple.nng.app/docs/ASSESSMENT.md`, `docs/BUSINESS_RULES.md`, `snippets.json`, and both
`customer.ple.nng.db.ETSPii/docs/ASSESSMENT.md` and `docs/PREFLIGHT.md`; plus 60 SQLite cells
across `gr`, `gr_scenario` and `gr_edge_case`. `projects.json` carried the placeholder
`National Fuel Gas (NNG)`, which is not the real client name.

The form that escaped Pass 1, for the record, as it appeared in `gr.sme_question`:

    Is suppressing the customer service representative contact for
    Northern-Natural-Gas-operated points intended, and should a missing
    representative contact on an outside company ...

and after Pass 3:

    Is suppressing the customer service representative contact for NRG-operated
    points intended, and should a missing representative contact on an outside
    company ...

## Interfaces and Dependencies

No new libraries. The script uses only the Python standard library — `os`, `re`, `sqlite3`, `sys`
— and was run on Python 3.14. The API validation needs the .NET SDK; `dotnet --version` reported
10.0.204.

**The one thing that will undo this work.** `platform-ui/tools/prepare_data.py` regenerates
`platform-ui/data/` from an analysis workspace, and it hardcodes the NNG engagement in constants
near the top of the file:

    DEFAULT_ANALYSIS = REPO_ROOT / "repos" / "nng-app-legacylift-analysis"          # line 57
    SYSTEMS = [
        SystemSpec("customer.ple.nng.app", "PLE Application", "application"),        # line 112
        SystemSpec("customer.ple.nng.db.ETSPii", "ETSPii Database", "database"),     # line 113
    ]
    PROJECT = {
        "projectId": "nng",                                                          # line 117
        "name": "NRG — Pipeline Location Engine",                                    # line 118
        "client": "National Fuel Gas (NNG)",                                         # line 119
        ...
    }

Re-running it restores every NNG name. There are two ways to live with that, and choosing between
them is one of the open `Progress` items. Either treat this plan as the post-processing step and
run the script after every regeneration — which is why the script is idempotent and takes the data
directory as an argument — or change those constants so `prepare_data.py` emits NRG-branded output
directly. The second removes the need for this plan on future regenerations but bakes a specific
client's rebranding into a tool whose stated job is faithful copying, and it would still not
rewrite the client name inside the generated *content* the tool copies, only the catalog around
it. The script would still be needed for the 20,648 in-content occurrences.

Related but deliberately untouched: the upstream corpora. Five `ASSESSMENT.md` files under
`repos/nng-app-legacylift-analysis/` still name the client —
`analysis/customer.ple.nng.app/ASSESSMENT.md` (2 hits),
`analysis/customer.ple.nng.db.ETSPii/ASSESSMENT.md` (1),
`analysis-domains-enhanced/customer.ple.nng.app/ASSESSMENT.md` (1) and
`analysis-semantic-search-enhanced/customer.ple.nng.app/ASSESSMENT.md` (1). `CLAUDE.md` records
that whole tree as gitignored, local-only, and holding generated corpora the active ExecPlans
describe as unreproducible. Do not rebrand or overwrite them without an explicit decision; see the
Decision Log.

## Revision note

2026-09-15, initial version, authored by Claude at Darrell Norton's request immediately after
performing the work. Written because `platform-ui/data/` is gitignored, so the three hand passes
that produced the current state exist nowhere in version control and would be lost the moment the
folder is regenerated. The three passes are consolidated here into one idempotent script rather
than transcribed sequentially, because the sequence included a defect — Pass 1's space-separated
literal missed the hyphenated client name, and Pass 1's verification shared the same literal so it
reported clean — and a plan that reproduced the sequence faithfully would reproduce the defect.
The consolidated script was validated by replaying it from a pristine pre-rebrand copy and
diffing against the hand-rebranded folder; that comparison is recorded under
`Validation and Acceptance` and is what found the CRLF-flattening bug now noted in
`Surprises & Discoveries`.

Writing the plan also changed the work. Three acceptance numbers drafted from earlier session
measurements did not survive being run as written — the `ETS*` preservation grep listed four
alternatives but had been measured with seven, and the sample-data count was taken across every
column rather than the one the command queries — and both are corrected in place rather than
noted, since a plan whose transcripts do not reproduce is worse than no transcript. More
importantly, running the residue check as a raw-file `grep` instead of a SQL query exposed a
de-identification hole that all three hand passes had left and all three verifications had
certified clean: 654 occurrences of the client's name in freed SQLite pages. `VACUUM` is now part
of the script, the fix has been applied to the live stores, and check 1 under
`Validation and Acceptance` deliberately greps the `.sqlite` files as binary.
