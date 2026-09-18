# Extraction gap detection — tell an engagement what Layer 0 is not looking at

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds, and every
revision must leave the file self-contained.

This repository's ExecPlan conventions live in [`docs/exec-plan.md`](../../exec-plan.md); this
document must be maintained in accordance with it. There is no `PLANS.md` at the repository root.

**Companion audit trail.** The design here was settled by a five-round interview on 2026-08-31 and
2026-09-01 plus an independent accuracy review, producing twenty-seven numbered decisions recorded in
[`pending/layer0-extraction-gap-detection-decision.md`](../pending/layer0-extraction-gap-detection-decision.md).
That file is the *why*: the alternatives that were rejected and the measurements that rejected them.
You do **not** need it to implement this plan — everything required to build and verify the feature
is here — but you must consult it before proposing a change to the design, because the interview may
already have considered and rejected it. This follows the precedent of
`active/reqs-to-data-store-additional-info.md`. Where this plan and the record disagree on a number,
this plan wins: its figures were re-measured on 2026-09-01 with the committed probe described below,
and two of the record's rounded values are stale (see `Surprises & Discoveries`).

**The measurements are reproducible from a committed script.** Every number in
`Validation and Acceptance` comes from
[`active/artifacts/gap-detection-probe.py`](./artifacts/gap-detection-probe.py), which
implements the settled walk and prints each corpus's expected result next to the measured one. Run
the probe before you start and again whenever a number surprises you; a disagreement is then a bug
in one place rather than an argument.

## Purpose / Big Picture

Layer 0 — the `legacylift-search` indexer — decides what to open using an allow-list of file globs.
Anything the allow-list does not name is never read, never lands in the database, and therefore
cannot appear in any query, any coverage percentage, or any report the platform produces. Nothing in
the toolchain says so. The effect is that every coverage figure LegacyLift has ever printed is a
percentage of the files the indexer already agreed to look at.

After this change a user runs one command and sees what is missing:

    legacylift-search gaps --repo-root repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app

and gets a table that says, in a few seconds, that 276 files and 805 KB of this application's own
source — 19.60% of the bytes it declared an intention to analyze — were never opened, that 178 of
those files are JSPs carrying display and validation logic, that four keystores are present and
unread, that 482 files were excluded on purpose and under which glob, and that five indexed files
produced no symbols at all. A second corpus, `repos/ctcm/ctcm-api`, reports 3.15% and names a Word
template that 57 of its 58 siblings are bound to by a constants class while that one is referenced
by nothing.

That is the user-visible outcome: a number that was previously unobtainable, a ranked list of what
produces it, and enough classification per row to tell "add a glob" apart from "write an extractor"
apart from "this is correctly invisible."

**What this plan deliberately does not do.** It does not close the gap. It does not add file
extensions to the indexer, write new parsers, or gate any command. It measures, names and ranks;
deciding what to do about each finding stays a human judgment made with the report in hand.

## Progress

- [x] (2026-09-01) Design settled: 27 decisions, both blockers closed, recorded in
      `pending/layer0-extraction-gap-detection-decision.md`.
- [x] (2026-09-01) Measurement probe committed at `active/artifacts/gap-detection-probe.py`;
      reproduces every acceptance number on both corpora.
- [x] (2026-09-01) Draft rewritten into this conforming ExecPlan; acceptance criteria pinned against
      both corpora; the `--own-identity` question the record left open is resolved in the
      `Decision Log` below.
- [x] (2026-09-01) M0 de-risked ahead of implementation: `languages.yml` and `vendor.yml` fetched and
      every resolution this plan pins verified against them (see `Artifacts and Notes`).
- [x] (2026-09-01) Test baseline established on this branch: **408 collected, 408 passing, exit 0**,
      run with `PYTHONPATH` pointed at the worktree's own `src/` — see the worktree trap in
      `Surprises & Discoveries`, which produced four phantom failures before the baseline was
      correct. Every milestone below adds tests to this number and must not reduce it.
- [x] (2026-09-02) Pre-implementation verification pass against the code, both corpora and live
      upstream: every line reference in this plan re-confirmed, both probe runs reproduced exactly,
      all M0 volumes and resolutions re-measured, `repo_files` = 1,229 / 4,715 confirmed, and the
      408-test baseline re-collected. It found eight defects in this plan's own specification — not
      in the design — and all eight are fixed in the revision you are reading; the four that were
      factual are recorded in `Surprises & Discoveries`.
- [x] (2026-09-02) Second verification pass, looking for what the first missed and for consequences
      the first pass introduced. Six findings, five fixed in the revision you are reading: the
      linguist commit SHA the M0 volumes were measured against is now recorded and pinned in Step 1
      (it was nowhere in the plan, the record or the probe, which made M0 unbuildable as written);
      the CLI snippet now gates the store open on `--mode` and wraps `resolve_paths`; `matched_glob`
      has an attribution rule; the `max_file_bytes`/observed-only contradiction is corrected; and
      the claim that ctcm-api exercises predicted mode is retracted in both the plan and the probe.
      The sixth was a design choice rather than an error and was decided with the maintainer the
      same day: `mode=ro` on a WAL index creates sidecar files, so the read-only open is kept as
      `mode=ro` for concurrent-writer safety and the "writes nothing" claim is narrowed to
      "modifies no data" — see the `Decision Log`. Nothing from this pass is left open.
- [x] (2026-09-02) Third pass, run as a pre-flight blocker check on M0 rather than a re-review of the
      design: **no blockers**. Verified live — the two-step fetch reaches `api.github.com` and
      `raw.githubusercontent.com`, `--ref d5214e16…` resolves to itself and to the recorded
      2026-09-01T09:40:55Z, and all five M0 volumes (`833 / 1,486 / 419 / 113 / 55`) and every pinned
      extension, filename and absence resolution reproduce at that SHA; the three tree-sitter traps
      behave as documented; `pyyaml` 6.0.3 is already in the venv; `packages.find where=["src"]`
      keeps `scripts/` unpackaged and `package-data` already ships `profiles/*.json`; none of the
      three new M0 paths is gitignored; both probe runs reproduce their expected lines exactly; and
      the suite still collects 408. It found three under-specifications in M0 — extension case,
      `LinguistLanguage.type` optionality, and the unenforced byte-reproducibility claim — all three
      fixed in the revision you are reading, none of which moves a pinned number.
- [x] (2026-09-02) **M0 shipped.** `scripts/refresh_linguist.py`,
      `src/legacylift_search/profiles/linguist.json` (254 KB, generated at
      `d5214e1612c858ba14bf98edeca57e1683276f1d`), `src/legacylift_search/linguist.py` and
      `tests/test_linguist_profile.py` (18 tests). All five pinned volumes reproduced on the first
      run — `833 / 1,486 / 419 / 113 / 55` — as did every pinned extension, filename, absence, case
      and tree-sitter resolution. A second generation to a scratch path is **byte-identical**, so the
      reproducibility claim is now checked rather than asserted. `pyproject.toml` is untouched:
      `packages.find where=["src"]` leaves `scripts/` unpackaged, `package-data` already ships
      `profiles/*.json`, and `pyyaml` stays out of the runtime dependencies.
      Suite: **408 → 426 passing, exit 0** (the 18 new tests and nothing else).
      Implementation found two defects, both recorded in `Surprises & Discoveries`: this plan's own
      acceptance criterion "833 languages, asserted from the vendored JSON" is impossible for a
      pruned profile (fixed additively with an `upstream_language_count` field), and writing LF is
      not sufficient to *keep* LF under this repository's `core.autocrlf=true` (fixed by a scoped
      `.gitattributes`, which is a new file at the repository root).
- [x] (2026-09-02) **M1 shipped.** `src/legacylift_search/gaps.py` (the walk) and
      `tests/test_gaps_walk.py` (28 tests), plus the two additive `DomainsFile` fields and two tests
      for them. Both corpora reproduce through `walk_repository` itself — every tier row, both KB
      conventions (including ctcm-api's 21,918), both headlines, the drop attribution 29/12/31 and
      3/2, all eight NNG gap-by-extension rows, and exactly the two pinned rescued `.tld` paths. The
      label assertions the probe cannot make also hold: all 276 and 186 gap files carry
      `rejected_by="include_globs"`, every one of NNG's 482 first-party files carries a
      `matched_glob`, and 0 of the 6,653 emitted paths on both corpora contains a backslash.
      Suite: **426 → 456 passing, exit 0**.
      The walk was built and unit-tested by two agents working from this plan in parallel, one
      forbidden from reading the other's file, so the tests are an independent reading of the spec
      rather than a mirror of the implementation; they passed against it on the first run. An
      adversarial conformance pass then cleared all fourteen specified properties and found three
      defects in **this plan** rather than in the code — recorded below, one of which needed a
      maintainer decision and got one.
- [x] (2026-09-08) **Coverage widening shipped, out of milestone order and deliberately so** — it had
      to land before the requirements plan's Step 10 Phase 1 rebuilt the index, because an extraction
      run over the pre-widening index would have measured its own coverage against a denominator that
      excluded 19.60% of NNG's first-party bytes and certified itself complete having never been shown
      the JSP layer. Eight `include_globs`, seven language-registry entries, `_CHONKIE_SKIP_LANGUAGES`,
      and `provenance.ThirdPartyClassifier` — extracted from `gaps.py` so that `discover_source_files`
      applies the walk's three third-party rules instead of approximating them with path globs, which
      it cannot: nine vendor `.tld` and two client `.tld` share one NNG directory and only the declared
      `<uri>` separates them. NNG's gap goes **19.60% → 0.00%** of first-party bytes for **+4.4%** index
      wall clock; discovery goes 1,229 → **1,504** files (`1,229 - 1 + 276`). ctcm-api moves
      4,715 → **4,722**, all `.xml`. Suite **1,207 → 1,250**, exit 0.
      Six decisions were taken with the maintainer and are in the `Decision Log`; the measurements are
      in `Surprises & Discoveries` under *The 2026-09-08 coverage widening*. **M3's acceptance numbers
      moved and are re-pinned** (see `Plan of Work > M3`); **M0–M2/M4's did not**, because
      `active/artifacts/gap-acceptance-manifest.json` now pins the historical 27 `include_globs` that
      previously fell through to the live default. Two consequences are filed as entries 9–10 of
      `pending/deferred-small-items.md`, and the deferred credential gate as
      `pending/indexer-credential-gate.md`.
- [ ] **M2 — the `gaps` command** (next): check one, rich table, `--json`, both headlines, observed
      and predicted modes. Start at `Plan of Work > M2`, which now carries the field-by-field split of
      what M1 already computed, the six measured CLI traps, and the two questions the pinned runs do
      not answer. `Interfaces and Dependencies` carries the as-built `gaps.py` surface — read that
      rather than the source. The suite floor is **1,250**, not the 456 this plan recorded before
      the branch merged into `feature/reqs-to-data-store` on 2026-09-03, which brought that branch's ~750 tests with it
      — 1,159 + M0's 18 + M1's 28 + the 2 `DomainsFile` tests. The acceptance fixtures and runners are
      committed in `active/artifacts/`, and `Validation and Acceptance > M1` now carries exact byte
      totals for both corpora so no rounding has to be re-derived.
- [ ] M3 — check two (`repo_files LEFT JOIN symbols`, `--min-bytes`) and the referenced-content
      reference count, both of which need the index connection.
- [ ] M4 — `**/legacylift-docs/**` into the manifest defaults and the `modernize-assess.md` wiring.

## Surprises & Discoveries

- **Observation: the KB column in the decision record's §3.I NNG table does not add up, and the two
  rows that are wrong are `gap` and `asset`.** §2 of that record makes "the displayed total is the
  sum of the displayed rows" a load-bearing convention — a reader must be able to add the column —
  and §3.I violates it by two.
  Evidence: re-measured 2026-09-01 with the committed probe, `gap` is **805 KB** (not 804) and
  `asset` is **1345 KB** (not 1344). 3301 + 805 + 2669 + 0 + 1345 + 41 = 8161, the stated walk
  total; with the record's values it comes to 8159. File counts, line counts, the walk total and both
  headlines are unaffected. **This plan pins 805 and 1345.**

- **Observation: the design has six tiers, not five.** The record's §3.D and Q22 say five
  (`indexed → credential → referenced content → excluded-by-design → gap`), which was true before
  Q27 split exclusion into two axes and made *first-party excluded* a named tier of its own,
  distinct from the asset tier that "excluded-by-design" originally meant.
  Evidence: the probe's tier order is
  `indexed → credential → referenced content → asset → first-party excluded → gap`, and §3.I's own
  NNG table prints six rows. Both corpora reconcile only against six.

- **Observation: 40% of NNG's third-party drops, and 60% of ctcm-api's, come from reading an identity
  the file declares about itself — a rule no path-based list can replace.** On ctcm-api the three
  files it drops are EDI schemas declaring `http://iaiabc.org/Schema`, a standards body; ctcm-api has
  no `vendored_globs` at all, so without this rule they become gap findings.
  Evidence: attributing each drop to the rule that made it —

        nng    declared-identity 29   vendor.yml 12   vendored_globs 31   (= 72)
        ctcm   declared-identity  3   vendor.yml  2   vendored_globs  0   (= 5)

- **Observation: `vendor.yml`'s filename patterns classify `.gitignore` and `.gitattributes` as
  third-party.** They are first-party repository metadata — material for the *first-party excluded*
  tier, not for a drop. This is the only imprecision found in the 113 adopted filename patterns
  across both corpora, and it is accepted rather than special-cased; a hand-maintained exception list
  is exactly the denylist §5 of the record warns against.
  Evidence: `vendor.yml         (^|/)\.gitattributes$   .gitattributes` in the drop attribution above.
  **Corrected 2026-09-02, because the cost was previously stated as "two small files on ctcm-api"
  and that is only the smaller corpus's share.** On NNG it claims **nine** files — `.gitattributes`,
  the root `.gitignore` and seven per-module ones — which is 9 of that corpus's 12 `vendor.yml`
  drops. Two consequences follow and neither changes a pinned number, but both will confuse someone
  reading the output: these nine appear under `dropped` rather than in the first-party excluded
  tier, and `NNG_FIRSTPARTY`'s own `**/.gitignore` and `.gitattributes` entries are therefore
  **dead patterns** — provenance (step 2) runs before tiering (step 3), so the drop has already
  happened by the time the first-party list is consulted. Expect them to claim zero files in
  `first_party_excluded_by_glob`.

- **Observation: running `pytest` from this worktree with the shared virtual environment tests the
  *other* branch's source code, silently.** The venv lives only in the main checkout
  (`tools/legacylift_search/.venv`) and its editable install resolves `legacylift_search` to the main
  checkout's `src/`, which is on a different branch. The suite still runs; it just does not test what
  you edited.
  Evidence: `import legacylift_search` from inside the worktree printed
  `...\legacylift-ai\tools\legacylift_search\src\legacylift_search\__init__.py`, and the suite showed
  four failures that vanished once `PYTHONPATH` pointed at the worktree's `src/`. The fix is in
  `Concrete Steps`; use it for every test run.

- **Observation: the acceptance numbers are post-M4 numbers, measured before M4 ships.** The probe
  adds `**/legacylift-docs/**` to the manifest exclusions from its first line, so the pinned figures
  already assume the M4 change. Run M2's acceptance against stock manifest defaults and ctcm-api
  reports **77.9% of bytes** with LegacyLift's own generated output as its largest finding — not a
  regression, just the pre-M4 configuration.
  Consequence, and it is a step you must not skip: M1–M3 acceptance is run with a manifest that adds
  that glob explicitly (`Concrete Steps` gives the file). M4 then makes it a default and the numbers
  do **not** move — which is M4's acceptance criterion.

- **Observation: `.xml` appears on both sides of the partition** — 183 indexed and 8 in the gap on
  NNG. Those 8 pass language detection and fail only `include_globs`: XML that is not `*.hbm.xml`,
  `*-flow.xml`, `spring/**` or `config/**`. The fix for that row is "add a glob", and it was
  invisible before this report existed. It is the clearest case for labelling each finding with the
  gate that rejected it.

- **Observation: linguist and tree-sitter disagree in both directions, which is why the report
  carries both columns.** `.dtd` is unknown to linguist but has a tree-sitter grammar; `.jsp` is
  known to linguist (`Java Server Pages`, `programming`) and has no grammar. Neither column subsumes
  the other, and the pair is the triage.
  Evidence: `detect_language_from_extension("dtd") -> "dtd"`, `has_language("jsp") -> False`,
  `.tld`/`.dtd`/`.vm`/`.ent`/`.mf` all absent from `languages.yml`.
  A third case sits between them and the column must not overstate it: `.xmi` is `XML`/`data` to
  linguist and `detect_language_from_extension("xmi")` is `None`. There *is* an XML grammar; nothing
  claims that extension. So the grammar column answers "a grammar is registered for this extension",
  never "this content could be parsed" — which is the honest reading, and the one that keeps
  `.xmi` a triage decision rather than a silently-answered question.

- **Observation: `cli_helpers.open_store_or_exit` cannot be used by `gaps`, because it exits 1 on a
  missing index.** This plan named it as the way to reach the store while also requiring that the
  command work before `index` has ever run and never exit nonzero — three requirements that cannot
  all hold. Resolved by resolving paths with `resolve_paths` and checking existence inline, and by
  pinning `--mode` behaviour in a three-row table rather than in prose.
  Evidence: `cli_helpers.py:135-140` raises `typer.Exit(code=1)` when `sqlite_path` is absent, after
  printing a "missing: index not found" message shaped for `stats`.

- **Observation: `SQLiteStore` has no read-only mode, so this plan's read-only claim was aspirational.**
  `_connect` calls `sqlite3.connect(str(self.sqlite_path))` at `store.py:175` — a read/write handle
  — and `migrate()` sets `journal_mode=WAL`, which writes sidecar files. Resolved by adding an
  additive `read_only: bool = False` keyword in M3 rather than by softening the claim.

- **Observation: and that resolution is still not enough — `?mode=ro` on a WAL database creates
  files.** Opening read-only does not make the command write-free, because a WAL reader needs the
  `-wal` and `-shm` sidecars and SQLite will create them if they are absent. Every LegacyLift index
  is WAL (`migrate()` sets it, and the mode is persistent in the file header), and a clean writer
  shutdown *deletes* both sidecars — so "absent" is the normal resting state of a finished index,
  not an edge case.
  Evidence, measured 2026-09-02 against a WAL database closed cleanly (sqlite 3.45.3):

        sidecars after clean close: wal=False shm=False
        ro read ok: [('a',)]
        sidecars after ro read:    wal=True  shm=True

  Adding `&immutable=1` is the only form that writes nothing (`wal=False shm=False` after the same
  read), and a plain `mode=ro` handle does correctly refuse writes
  (`OperationalError: attempt to write a readonly database`). Confirmed on the real NNG index too:
  both URI forms read `repo_files` = 1,229, and a Windows path with backslashes works unmodified in
  the URI, so no `as_posix()` conversion is needed.
  Two live consequences: the `Idempotence and Recovery` claim that the read-only open makes
  "writes no artifact… mutates nothing" *structural* was false as written, and a `gaps` run against
  an index on a read-only filesystem or in a locked-down directory will fail to open it at all
  rather than degrade. Resolved by keeping `mode=ro` — concurrent-writer safety is worth more here
  than a literal write-free claim — and narrowing the claim to "modifies no data", which is what is
  actually true. The reasoning and the rejected `immutable=1` alternative are in the `Decision Log`.

- **Observation: NNG's live `domains.json` is still the pre-split file, and `--domains` defaulted
  straight to it.** Measured 2026-09-02: `exclude_globs` 45, `vendored_globs` 0, `own_identities`
  absent — exactly the 45-pattern mixture Q27 re-classified. The default therefore pointed at a file
  that reproduces none of this plan's numbers and says nothing about it. Resolved by a mandatory
  degraded-provenance warning plus `provenance_degraded` / `domains_source` in the payload, and by
  `--domains none`. The underlying cause is the follow-on already named in `Artifacts and Notes`:
  nothing authors `own_identities` yet.

- **Observation: the probe is the oracle for the numbers, not for the labels.** It applies
  `include_globs` and tiers immediately (`gap-detection-probe.py:252-253`), so it implements neither
  the `detect_language` gate nor the `max_file_bytes` gate and carries no `rejected_by`. Every
  label this plan specifies is therefore unit-test territory, and the `Interfaces` block originally
  had nowhere to put those labels at all — `GapReport` carried no gap-file list and `ExtensionRow`
  no label field, which made "label each finding with the gate that rejected it" unreachable from
  the specified types. Fixed by `gap_files`, `ExtensionRow.rejected_by`, `WalkedFile.matched_glob`
  and `first_party_excluded_by_glob`.

- **Observation: the two gates the walk models disagree about case, and the walk must reproduce the
  disagreement rather than smooth it over.** `detect_language` casefolds (`languages.py:105,117`),
  but the allow-list does not: `pathspec`'s gitignore dialect is case-sensitive, verified
  2026-09-02 — `**/*.java` matches `a/foo.java` and does **not** match `a/FOO.JAVA`. So an
  upper-case-extension file can fail `include_globs` while the language gate would have accepted it,
  and it must be labelled `rejected_by="include_globs"`, never `"language"`. A walk that casefolded
  the glob side to "be consistent" would reclassify exactly those files and disagree with the indexer
  it exists to measure. The corpora make this cheap to get wrong and cheap to check: NNG's only
  mixed-case extension is `.MF` (14 `MANIFEST.MF` files) and ctcm-api has none at all, so no pinned
  number in this plan moves under the casefold rule stated in M0 — which is precisely why it had
  to be written down rather than discovered later on a third corpus.

- **Observation: "833 languages" is not assertable from the vendored JSON, because pruning removes
  six of them — and the acceptance criteria asked for exactly that.** The profile keeps only the
  extension and filename maps, so a language that upstream identifies by neither is not reachable
  through either and prunes away completely. Measured at the pinned SHA on 2026-09-02: `languages.yml`
  holds 833 languages, 6 of which carry neither an `extensions` nor a `filenames` list —
  `Elvish Transcript`, `Julia REPL`, `OpenAPI Specification v2`, `OpenAPI Specification v3`,
  `OpenRC runscript` and `Python console`, identified upstream by interpreter or by REPL shape — so
  the two maps carry **827** distinct names. The extension and filename key counts are unaffected
  (1,486 and 419, as pinned), because none of the six contributed a key in the first place.
  Resolved additively rather than by dropping the number: `refresh_linguist.py` writes
  `upstream_language_count` from `len(languages.yml)`, the model declares it, and the M0 test asserts
  **833 and 827 together**. That pair is worth more than either alone — 833 moving alone means
  upstream released, 827 moving alone means the inversion broke, and only the second is a bug in this
  repository. Asserting 827 by itself would have conflated them.
  Cost of the alternative, for the record: asserting only 827 leaves the fetch half of the refresh
  unchecked, which is the half that talks to the network.

- **Observation: writing the file with LF is not enough to keep it LF — this repository is
  `core.autocrlf=true` and had no `.gitattributes` at all.** M0's byte-reproducibility requirement
  named only the *writer's* newline default as the hazard, and fixing that leaves git free to undo
  it: the file is written LF, committed normalized, and handed back **CRLF** on the next checkout,
  at which point the determinism test fails and every future refresh diff is the entire file.
  Evidence, measured 2026-09-02: `git config core.autocrlf` → `true`, no `.gitattributes` anywhere in
  the tree, and the *existing* `profiles/extractors.json` is checked out **with CR** — so this is
  demonstrated behaviour on a sibling file in the same directory, not a theoretical risk.
  Resolved by a repository-root `.gitattributes` carrying one scoped line,
  `tools/legacylift_search/src/legacylift_search/profiles/linguist.json text eol=lf`. Verified by
  staging the file and materializing the checkout copy with `git checkout-index --temp`: no CR, and
  byte-identical to the working tree. Scoped to the one path deliberately — a repo-wide
  `*.json text eol=lf` would renormalize `extractors.json`, which is CRLF on disk today and is
  outside this plan.
  The test that catches a regression here is already written: `b"\r" not in raw_bytes` over the
  working-tree file fails loudly if a future checkout reintroduces CRLF, which is the right place for
  the guard.

- **Observation: `CheckResult.index` addresses `pathspec`'s *compiled* pattern list, not the list you
  passed — and this plan said the opposite.** The tier bullet below asserted that `index` is "the
  deciding pattern's position in the list you passed", which is true only for a list containing no
  comments and no whitespace-only lines. Measured 2026-09-02 against `pathspec` 1.1.1 / py3.12.9,
  feeding `["# a comment", "", "docs/**", "   ", "!docs/keep.md", "conf/*.properties"]`: six lines in,
  **five compiled** — the empty string is dropped while the comment and the whitespace-only line are
  *kept* as `include=None` null patterns. So the two lists diverge from the first blank line onward,
  and indexing the caller's list returns the wrong pattern (here, `""` instead of `docs/**`).
  The implementation reads `spec.patterns[index].pattern` instead, which round-trips the original
  text verbatim, `!` prefix included. Nothing in either corpus carries a comment in a glob list, so no
  pinned number was ever at risk — but a `domains.json` written by a human with a `#` comment in
  `exclude_globs` would have mis-attributed every `matched_glob` after it, which is precisely the
  column the report exists to print.

- **Observation: `DroppedFile` carried no bytes and no lines, which makes this plan's own raw headline
  unreachable from its own types.** The `Interfaces` block specified `relative_path / rule / detail`,
  and `WalkResult.totals` is keyed on `Tier`, which has no drop member — yet the acceptance table
  prints `third-party DROPPED 72 762 KB 20730 lines` and the `Decision Log` defines the raw headline
  over the tiers *plus the drops*. Confirmed arithmetic: `(4860+762)/(5622+3301) = 62.99%` and
  `(93282+20730)/(114012+92232) = 55.28%` — both need drop bytes **and** drop lines. Worse, the walk
  counted lines *after* provenance, so dropped files were never line-counted at all and M2 would have
  needed a second filesystem pass over them. Resolved additively in M1: `DroppedFile` gains
  `size_bytes` and `line_count`, and the line count moves ahead of the provenance block so every file
  is still read exactly once. The drop row now comes out of `walk.dropped` alone with no filesystem
  access — 72 / 762 KB / 20730 on NNG, 5 / 93 KB / 2139 on ctcm-api.
  **One rounding rule for M2 falls out of this and is not the one stated above.** That row's KB is
  `round(total_bytes / 1024)` computed once, not the sum of per-file roundings: measured, summing
  per-file gives 755 and 94, against the pinned 762 and 93. "The displayed total is the sum of the
  displayed rows" is a rule about *tier rows summing to the walk total*; it does not descend to
  individual files.

- **Observation: a keystore could be hidden after all — not by an image glob, but by the allow-list.**
  The tiering reached `credential` only after the `include_globs` branch failed, so with `**/*.p12` in
  `include_globs` a `.p12` landed in `gap` with `rejected_by="language"` and `credential_files` was
  silently empty. The M1 `indexed` bullet specified exactly that ("falls through to `gap`
  carrying…"), while `What must not happen` says the credential tier outranks every other non-indexed
  tier "precisely so a keystore can never be hidden" — and `gap` is a non-indexed tier. Two binding
  sections, opposite answers. Neither corpus exposes it, because no default `include_globs` pattern
  names a credential extension; the trap fires the moment someone widens the allow-list, which is the
  very action the `language` label exists to encourage. Decided by the maintainer 2026-09-02 in favour
  of the security reading — see the `Decision Log`. No pinned number moves.

- **Observation: eleven of NNG's first-party globs claim zero files, not the two this plan predicts,
  and the four causes are worth telling apart.** The `.gitignore`/`.gitattributes` entry above
  predicts two dead patterns. Measured against the shipped walk, the full list is eleven, and
  "claims zero files" turns out to mean four different things: **571 files eaten by the manifest gate**
  before tiering (`*/bin/**` 507, `**/.settings/**` 56, `**/build.xml` 8); **11 dropped as
  third-party by `vendor.yml`** before tiering (`**/.gitignore` 8, `.gitattributes` 1, `gradlew.bat`,
  `Jenkinsfile` — which is 11 of that corpus's 12 `vendor.yml` drops); **52 claimed by the asset tier**,
  which outranks first-party excluded (the `content/images/**` path 51, `**/favicon.ico` 1); and
  `legacylift-docs/**`, which matches no file in this corpus at all. The eleventh,
  `**/.apt_generated/**`, is not dead in any sense — its 8 files *are* first-party excluded, attributed
  to a later pattern that won the last-match rule. That last case is the useful one: it demonstrates
  gitignore precedence working, and it means an absent row in `first_party_excluded_by_glob` is not
  evidence that a pattern is useless. Expect eleven absent rows on NNG and someone to ask why.

- **Observation: NNG's 45 stored patterns are 43 re-classified plus 2 deliberately deleted, and this
  plan's phrasing hides the deletion.** `NNG_VENDORED` (10) and `NNG_FIRSTPARTY` (33) come to 43
  against the live `domains.json`'s 45, and this plan repeatedly says Q27 "re-classified" the
  45 — which sends a reader hunting for two lost patterns. The two are `db/**` and
  `ple-persistence/sql/**`, and the probe records why at `gap-detection-probe.py:98-102`: 25 files of
  Quartz DDL, FarmTap rollback and 16 data-cleanup queries that encode real data-quality rules, are
  indexed, and supply four of check two's eight M3 findings. They were removed from the exclusion
  list on purpose. Read 45 = 43 + 2, not 45 = 10 + 33.

- **Observation: "contents are never read or excerpted" cannot be true, because this plan pins the
  credential tier at 192 lines.** Line counting reads every surviving file whole, keystores included —
  that is what produces the `4 41 KB 192 lines` row. The claim that is actually true, and the one the
  credential rule needs, is that **no content is retained or emitted**: nothing from a credential file
  reaches `WalkResult`, the report, or `--json`. One narrower overlap exists and is a curiosity rather
  than a leak: `CREDENTIAL_NAMES` matches on the stem, so a file named `cacerts.xsd` or
  `ssTrustStore.dtd` is an identity candidate at step 2 — it is opened, and a substring of its
  contents can land in `DroppedFile.detail` — before tiering would have called it a credential at
  step 3. No real keystore carries those three extensions.

- **Observation: an ACL-unreadable file crashed the walk, ahead of the guard written for it.**
  `pathlib.Path.is_file` re-raises `EACCES` — only `ENOENT`, `ENOTDIR`, `EBADF` and `ELOOP` are
  ignored — so the `try/except OSError` wrapped around the walk's own `stat()` only ever caught the
  vanished-file race, never a permission-denied file. A `gaps` run over a tree containing one such
  file exited with a traceback, against the plan's rule that the only nonzero exit is a usage error.
  Fixed by guarding `is_file()` too. Two neighbouring read-failure behaviours are now pinned by test
  rather than specified by this plan, and both were chosen silently by the implementation: a file that
  stats but cannot be *read* stays in its tier with `line_count = 0`, while a file whose `stat()`
  fails leaves the walk entirely, recorded nowhere. The first inflates the byte denominator while
  contributing no lines. Predicted mode has no oracle for either, which is the plan's stated reason
  observed mode is more truthful — but the plan never said what predicted mode should *do*.

- **Observation: there is a second, entirely reachable route to the `language` label that this plan
  does not describe — a file with no extension.** M1 says the label becomes reachable "the moment
  someone widens the allow-list" to an extension `_EXTENSION_TO_KEY` does not know. But `Path.suffix`
  is `""` for `Dockerfile` and for dotfiles like `.editorconfig`, and `detect_language` returns `None`
  for an empty suffix (`languages.py:118-119`), so an `include_globs` entry of `**/Dockerfile` — a
  perfectly reasonable thing to add — produces `gap` / `rejected_by="language"` immediately.
  Measured on a fixture with `include_globs=("**/Makefile","**/Dockerfile")`: both files take that
  branch. It does not fire on either corpus because every default glob is `**/*.ext`, and ctcm-api's
  19 `Dockerfile`s are rejected one gate earlier, by `include_globs`. Untested and unpinned.

- **Observation: symlinks are counted twice in one direction and not at all in the other, and the
  walk agrees with `discover_source_files` on both — which is the only reason it does not matter.**
  Measured on Windows 11 / py3.12.9: a symlink *to a file* is walked as a file in its own right —
  `is_file()` follows it, `stat()` reports the target's size, and the target's bytes and lines are
  counted a second time, inflating the tier totals and both headline denominators. A symlink *to a
  directory* contributes nothing, because `rglob("*")` does not descend into one on 3.12 and the link
  entry itself fails `is_file()`. Neither corpus contains a symlink, and `discovery.py` uses the same
  two calls, so the walk and the indexer agree exactly and the divergence is zero. Recorded rather
  than fixed: a repository that symlinks a vendored tree would double-count it on both sides of the
  ratio, which is survivable, while "fixing" it unilaterally would make the walk disagree with the
  gate it exists to model.

- **Observation: `rescued_by_identity` is narrower than it reads, and records only one of the two
  rescues the identity rule performs.** A path lands there only when the extension is a candidate,
  an identity was found, it contained an own token, **and** a `vendored_globs` pattern would otherwise
  have claimed it. The other rescue — an own-identity file that `vendor.yml`'s filename patterns would
  have dropped — happens silently, because the identity branch short-circuits those patterns before
  they are ever consulted, and it is recorded nowhere. Measured: an own-domain `.tld` with no
  `vendored_globs` configured produces an empty list. So an empty `rescued_by_identity` does not mean
  the identity rule did nothing.

### The 2026-09-08 coverage widening

Measured while preparing the requirements plan's Step 10 Phase 1 index rebuild. That rebuild is a
one-shot, hours-long act, and these are the findings that had to land before it ran. Unless a row
says otherwise, the corpus is `customer.ple.nng.app`.

- **Observation: the widening is nearly a no-op on the second reference corpus, which is the good
  outcome and was not the expected one.** This plan's methodology exists because "every rule was
  fitted to one corpus, and first contact with a second broke two of them", so the eight new globs
  were measured against ctcm-api before being trusted. **+7 files, all `.xml`; 4,715 → 4,722.**
  ctcm-api is .NET and contains no `.jsp`, `.tld`, `.properties`, `.css`, `.vm`, `.ent` or `.xmi` at
  all, so seven of the eight patterns match nothing. The pre-widening `indexed` figure of 4,715 that
  M1 pins is unchanged, and there is no `.properties` credential exposure on this corpus.
  The seven files are EDI sample payloads under
  `src/CTCM.API/CTCM.API.EdiService/Xml/Samples/` (FROI/SROI workers'-comp claim documents, 2–13 KB
  each) carrying visibly synthetic identifiers — `123456789`, `987654321`, `DEMO` in the filenames.
  Worth indexing: they are the concrete shape of the EDI contract whose schemas the walk drops as
  third-party.
  Evidence: `discover_source_files` run against `repos/ctcm/ctcm-api` with the old 27 and the new 28
  globs, 2026-09-08.

- **Observation: `customer.ple.nng.db.ETSPii` is also nearly unaffected — 569 files, 568 `.sql` and
  one `.xml`.** It is a database unit; the widening's Java-web extensions do not occur in it. Its
  `domains.json` was given `own_identities: ["nngco.com"]` for consistency but no `vendored_globs`,
  which is an honest "unmeasured", not a claim that it has no vendored content.

So the widening's blast radius is concentrated almost entirely on the one corpus it was designed
against. That is a weaker validation than this plan usually demands — a second corpus that exercises
seven of eight patterns would be worth more — but it does establish that the change is not
destructive elsewhere.

- **Observation: an extraction run over the old index would have certified itself complete while
  never having been shown the JSP layer.** `/modernize-extract-rules` Step 0 says that when an index
  exists, the `business-rules-extractor` lenses query the index by intent instead of blind-sweeping
  the tree, and its round-over-round coverage metric is *chunk-level over indexed chunks*. The old
  27-glob allow-list left 276 files unindexed — 805 KB, 19.60% of first-party bytes, 178 of them
  `.jsp`. So the lenses would never see those files **and** the denominator would exclude them.
  Ironically, with *no* index the workflow falls back to grep over the whole tree, which would see
  them: the index made the run less complete and more confident.
  Evidence: the walk's headline on the pre-widening configuration, reproduced by
  `artifacts/gap-acceptance-walk.py`.

- **Observation: `.jsp`, `.css` and `.tld` hang the indexer indefinitely, and a registry entry alone
  is not enough for them.** Chonkie has no code grammar for these, so `prefer_ast_boundaries` sends
  them down its `language="auto"` detection path, which does not terminate. `chunking.py` already
  carried a hardcoded `source_file.language != "xml"` guard whose inline comment says exactly this —
  the comment is load-bearing and applies to four of the seven new languages.
  Evidence: measured against real NNG files, 2026-09-08 —

        .jsp        jamon-web/WebContent/exceptions.jsp   13,904 b   HUNG >600s (killed)
        .tld        (first .tld)                                     HUNG  >60s (killed)
        .css        (first .css)                                     HUNG  >60s (killed)
        .vm         contentFooter.vm                         144 b   13.80s -> 1 chunk
        .ent        xhtml-lat1.ent                        11,775 b    5.32s -> 15 chunks
        .xmi        ibm-web-bnd.xmi                          290 b    0.71s
        .properties gradle-wrapper.properties                361 b    0.70s

  13.8 s to chunk 144 bytes is the same pathology, merely not yet unbounded. The fix is
  `_CHONKIE_SKIP_LANGUAGES`, pinned by `tests/test_coverage_config.py`.

- **Observation: grammar availability is irrelevant — `extractors.json` is the gate.**
  `extractors.py` returns an empty `ExtractedFile` for any language with no profile in
  `extractors.json`, *before* it ever reaches `_get_parser_for`. So `.css` and `.properties`, whose
  tree-sitter grammars load fine from `tree_sitter_language_pack`, behave identically to the five
  grammar-less extensions. **All seven newly-registered languages are symbol-dead.** Any framing
  that splits this work into "grammar exists → cheap" versus "no grammar → needs an extractor" is
  wrong and must not be carried forward.
  Evidence: the index log says so once per file — `PARSE_NOTE …: no extractor profile for language
  'jsp'` — and the measured symbol delta below is +21, all from `.xml`.

- **Observation: `supports_tree_sitter` is dead code.** Declared at `languages.py:29`, set on all
  eight pre-existing entries, and **read by nothing in the package** — only two assertions in
  `tests/test_discovery.py:79,83`. It is *not* the hook for the "expected to have no symbols" state
  that M3 needs; `extractors.json` profile presence is.

- **Observation: the widening is +4.4% index wall clock, and its cold-run cost was page cache, not
  the change.** A cold-cache trial took 690 s; a warm re-run took 335 s with byte-identical counts.
  Both trial runs produced identical numbers — deterministic.
  Evidence: three index runs. The **control** (today's code, old 27 globs) exists because the real
  index was built 2026-07-23 and months of unrelated drift sit between them; without it, five
  pre-existing SQL-extractor diffs would have been misread as regressions from this change.

  | | real index (2026-07-23) | control (today, old globs) | trial (today, new globs) |
  |---|---|---|---|
  | `repo_files` | 1,229 | 1,229 | **1,537** (+308) |
  | `chunks` | 15,040 | 15,052 | **15,534** (+482) |
  | chunks on new files | — | — | **482, 100% `chunk_kind='fallback'`** |
  | `symbols` | 16,272 | 16,282 | **16,303** (+21) |
  | `symbol_refs` / `graph_edges` | 74,289 / 74,552 | 74,296 / 74,559 | 74,306 / 74,569 |
  | files with 0 symbols | 36 | 36 | **331** |
  | 0 symbols **and** `size_bytes >= 2048` | 8 | 8 | **164** |
  | warm wall clock | — | 321 s | **335 s (+4.4%)** |

  New rows by extension (+308): `.jsp` 186 files / 698,764 b / 0 symbols / 241 chunks; `.properties`
  44 / 85,009 / 0 / 53; `.vm` 35 / 18,219 / 0 / 35; `.xml` 15 / 67,941 / **21** / 19; `.tld` 13 /
  285,320 / 0 / 88; `.css` 10 / 94,659 / 0 / 38; `.ent` 3 / 30,267 / 0 / 6; `.xmi` 2 / 804 / 0 / 2.
  Total 1,280,983 bytes, 482 chunks, 21 symbols — all from `.xml`, via the pre-existing
  framework-aware `xml_extractor`. **Regression against the control: clean.** Zero files stopped
  being indexed, zero lost symbols, per-file chunk and symbol totals identical on shared files, zero
  sha256 mismatches.

- **Observation: the walk auto-tracks the config change, so its 0.00% means what it looks like.**
  `gaps.py:walk_repository` reads `include_globs` **live**
  (`pathspec.PathSpec.from_lines("gitignore", project.include_globs)`) and calls `detect_language`
  live. Exactly the 276 moved into `indexed` (871 + 276 = 1147); the gap-by-extension table is empty.
  Evidence:

        HEADLINE      19.60% bytes / 17.55% lines  ->   0.00% / 0.00%
        RAW HEADLINE  63.00% bytes / 55.28% lines  ->  53.99% / 45.76%

- **Observation: what this buys is retrieval coverage, not graph coverage — which is nonetheless
  exactly what Step 10 needs.** 482 fallback text chunks reachable by FTS5 and vector search; 293 of
  308 new files contribute nothing to symbols, refs, edges or facts. The extraction lenses retrieve
  semantically and the coverage metric counts chunks, so this is the right shape.
  Consequence worth carrying: citations into these files resolve to the **file-level floor**, whose
  `anchor_key` is path-only and index-independent by design (`reqs-to-data-store.md` Decision Log,
  the `PR-82`/`PR-83` entry — "a constant cannot churn"), so they are stable. **But if anyone later
  authors a JSP extractor, those citations move from file-anchor to symbol-anchor, changing
  `dedupe_key` tier 1 and re-keying every rule that cites JSP.** Recorded as entry 9 of
  `pending/deferred-small-items.md`. That churn is deferred either way; widening now at least means
  the rules exist to be re-keyed.

- **Observation: `**/*.properties` sweeps real cleartext credentials into the index, production
  among them.** Of NNG's 44 first-party `.properties` files, 15 carry 22 credential-shaped keys with
  literal values: `spring.cloud.config.password` (3 files, 3 distinct values, 25 and 50 chars),
  `hazelcast.group.password` (13 files, 1 shared value, 11 chars), and three keystore passwords of 8
  chars each (almost certainly the Java default `changeit`). `application-prod1.properties` is among
  them. The walk's `credential` tier cannot catch these — it is keyed on
  `.p12/.jks/.keystore/.pfx/.pem` plus the filenames `sstruststore`/`cacerts`, and **never reads
  contents** — and the indexer has no credential concept at all. So they land in `chunks`, in FTS5,
  and with a real embedding provider they are sent to Bedrock.
  Evidence: measured 2026-09-08 by key-name pattern over non-comment assignments, counting value
  lengths and distinctness without recording the values.

- **Observation: the widening made the indexer and the walk disagree about 33 files, and 13 of them
  cannot be reconciled by any path glob.** `**/*.tld` matches 13 NNG files where the walk's gap was
  2. Eleven are vendor descriptors — but nine of those sit in the **same directory** as the two
  client tag libraries, `ple-web/src/main/webapp/WEB-INF/tld/{naesb,nngauthz}.tld`. Only the declared
  `<uri>` separates them: the client pair declare `http://www.nngco.com/...`, the rest declare
  springframework.org, java.sun.com, displaytag.sf.net, joda.org and tiles.apache.org. The remaining
  two vendor files (`ple-arch-properties/xmlcatalog/spring{,-form}.tld`) are covered by no
  `vendored_globs` pattern at all and are caught only by identity.
  Evidence: full disagreement, measured 2026-09-08 — 13 `vendored_globs` (11 `.tld` + 2 jquery
  `.css`), 2 `declared_identity` (the xmlcatalog pair), 20 `first_party_excluded` (8 `jamon-web`
  `.jsp` + its `web.xml` + 2 JAMon `.css`; 5 `ple-ear` deployment descriptors; 2 `ple-services-test`
  Spring contexts + its `log4j2.properties`; `gradle-wrapper.properties`).

- **Observation: excluding those 20 by directory would have dropped 358 currently-indexed files.**
  The obvious fix — adding `jamon-web/**`, `ple-ear/**`, `ple-services-test/**` and `gradle/**` to
  the manifest's `exclude_globs` — costs 332 `.java` and 25 `.sql` files that are indexed today, to
  suppress 20. The exclusions must be extension-scoped.
  Evidence: measured against the pinned acceptance manifest before making the change.

- **Observation: the live `domains.json` files carry neither `vendored_globs` nor `own_identities`.**
  Both fields existed only in this plan's hand-authored acceptance artifact
  (`artifacts/gap-acceptance-domains-nng.json`). Wiring the indexer at the live file would therefore
  have built no classifier and filtered nothing, silently. Populated on both NNG units 2026-09-08.
  **`/modernize-assess` does not author either field** — it learned to author `exclude_globs`
  (see the domain-enhancements plan) but not these. Until it does, they are hand-maintained, which
  is entry 10 of `pending/deferred-small-items.md`.

- **Observation: pinning `include_globs` in the acceptance manifest was necessary, not tidy-up.**
  `artifacts/gap-acceptance-manifest.json` pinned **only** `exclude_globs`, so `include_globs` fell
  through to the live `ProjectConfig` default — which the widening then changed. M0–M4's acceptance
  criteria pin the gap tier at 276 files / 19.60%, so without the pin the detector would report
  0.00% against its own primary corpus and read as having lost its discriminating power.

## Decision Log

Twenty-seven decisions (Q1–Q27) were settled by the design interview and the accuracy review, and
they are recorded with their rationale and rejected alternatives in
`pending/layer0-extraction-gap-detection-decision.md` §3 and §4. They are not restated here; the
`Context and Orientation` and `Plan of Work` sections below describe what to build, which is their
outcome. The entries below are decisions made **while writing this plan**, which are therefore not in
that record.

- Decision: **Declared-identity provenance is consulted only when at least one "own identity" token
  is supplied**, via `--own-identity` (repeatable) or an `own_identities` list in `domains.json`.
  With no token, the rule is skipped entirely and provenance falls through to `vendor.yml`'s filename
  patterns and then `vendored_globs`.
  Rationale: the record settles that declared identity is authoritative in *both* directions — a file
  naming the client's own domain is first-party even when a vendored glob claims it — but never says
  where the client's domain comes from. The probe hard-codes it per corpus. Taken literally with an
  empty token set, "authoritative in both directions" makes every file that declares any identity
  third-party, which would silently delete `nngauthz.tld` — the exact file Q27 exists to rescue, and
  a real access-control rule bound to `com.nng.ple.web.tags.NngAuthorizeTag`. Skipping the rule
  instead fails toward *reporting*: an unrecognised third-party schema shows up as a gap finding,
  which is noisy but visible, and the record's §5 is unambiguous that only a walk which reports the
  unknown can find the unknown.
  Measured cost of omitting the flag, 2026-09-01, running the walk with the identity rule skipped.
  On ctcm-api it is plain: the three `iaiabc.org` EDI schemas fall through, drops 5 → 2, gap
  186 → 189 files, headline 3.15% → 3.85% of bytes. On NNG it is more interesting and worth reading
  twice — **the file counts do not move at all**, drops staying at 72 and the gap at 276, while the
  composition changes underneath them: `naesb.tld` and `nngauthz.tld` are deleted by the
  `WEB-INF/tld/**` pattern, and two third-party files that no glob covers leak into the gap in their
  place. Only the bytes give it away (drops 762 → 702 KB, gap 805 → 865 KB, headline 19.60% → 20.76%
  of bytes and 17.55% → 19.10% of lines). That is a small worked example of why this plan counts
  bytes and lines rather than files alone, and why the two rescued files are named individually in
  the M1 acceptance criteria instead of being checked by a count.
  Both acceptance runs therefore pass the flag, and both then reproduce the probe exactly.
  Date/Author: 2026-09-01, plan author.

- Decision: **The two authored glob lists are read from `domains.json` directly, via `--domains`, and
  no new table is added to `knowledge.sqlite`.**
  Rationale: `knowledge.sqlite` persists only `exclude_globs`, through `set_exclusions()` /
  `list_exclusions()`, and on the reference corpus that stored list is the *pre-split* 45-pattern
  mixture that Q27 found conflates both axes. Using it as the first-party list would tier files that
  must be dropped and reproduce none of the pinned numbers. `domains.json` is where both lists are
  authored, `/modernize-assess` now emits both there, and reading the file directly keeps one source
  of truth and adds no persistence or staleness surface — consistent with Q21's refusal of a new
  artifact. `--domains` defaults to `<analysis_dir>/domains.json` when that file exists, so the
  `/modernize-assess` wiring in M4 needs no argument.
  Date/Author: 2026-09-01, plan author.

- Decision: **The raw (pre-suppression) headline is defined as every file surviving the manifest gate
  that is not in the `indexed` tier, plus the third-party drops, over `indexed` plus that** — and it
  is pinned to one decimal place, as an approximate check, while the post-suppression headline is
  pinned exactly.
  Rationale: §3.H requires both headlines so the suppression is visible rather than silently
  flattering, but the record's raw figures (536 files / 3,318 KB / 37%) were measured under the
  pre-Q26/Q27 configuration and are not comparable to anything the shipped walk computes. Defining
  raw over the shipped partition gives NNG 63.0% of bytes and 55.3% of lines against a post-
  suppression 19.60%/17.55%, which makes the suppression plainly visible — the property §3.H actually
  wants. The raw values in this plan are derived from the rounded KB column and so may differ from an
  exact-byte computation in the second decimal; that is why they are pinned coarsely.
  Date/Author: 2026-09-01, plan author.

- Decision: **The read-only connection uses `?mode=ro` and not `?mode=ro&immutable=1`, and the
  "writes nothing" claim is narrowed to "modifies no data" to match.**
  Rationale: measured 2026-09-02, `mode=ro` on a WAL database creates the `-wal` and `-shm` sidecars
  when they are absent — which is the resting state of a cleanly closed index, since a clean writer
  shutdown deletes them — so the first review round's read-only keyword did not make this plan's
  write-free claim structural the way it asserted. `immutable=1` does create nothing, but it tells
  SQLite the file cannot change, which makes reads undefined rather than merely stale if an `index`
  run is in flight. `gaps` is a diagnostic people will run *while* wondering whether to reindex, so
  it is exactly the command most likely to be pointed at a database being written. Concurrent-writer
  safety is therefore worth more than a literal write-free claim, and the honest fix is to narrow the
  claim: no row of any database is modified, and two sidecar files may appear. The one property
  genuinely lost is reading an index on a read-only filesystem; if that becomes a real requirement,
  `immutable=1` is added as an opt-in flag rather than promoted to the default.
  Date/Author: 2026-09-02, second verification pass, decided with the maintainer.

- Decision: **`DomainsFile` gains `vendored_globs` and `own_identities` in M1; nothing else in the
  domain-tagging path changes.**
  Rationale: `DomainsFile` (`domain_tagger.py:92-111`) sets no `extra="forbid"`, so pydantic already
  ignores both keys today — `/modernize-assess` has been emitting `vendored_globs` since commit
  `7b17fd0a` and `load_domains_json`, `tag-domains` and the domain-coverage denominator are
  unaffected by it. Declaring the fields is additive, needs no `schema_version` bump, no migration
  and no reindex. Adding them in M1 keeps the model change next to the code that first reads them.
  Date/Author: 2026-09-01, plan author.

- Decision: **Extension comparisons casefold; filename and glob comparisons do not.** The vendored
  JSON is keyed on casefolded extensions, `classify_extension` casefolds its argument, `M1`'s
  credential / asset / referenced-content sets are lowercase literals matched against a casefolded
  extension, and `WalkedFile.extension` stores the casefolded form. `classify_filename` and the
  `include_globs` / first-party-exclusion matching stay exact.
  Rationale: the plan specified neither, and three defensible readings existed. Casefolding
  extensions is not a preference but conformity with the gate being modelled — `languages.py:105`
  stores `ext.lower()`, `languages.py:117` looks up `path.suffix.lower()` — so a raw comparison
  would report a language verdict the indexer would not have reached. Rejected: **(a) key the JSON
  raw**, which splits `gap_by_extension` into `.PNG` and `.png` rows and makes NNG's 14
  `MANIFEST.MF` files depend on the spelling on disk; **(b) casefold the glob side too, for
  consistency**, which is the harmful one — `pathspec`'s gitignore dialect is case-sensitive, so
  this would admit files the real allow-list rejects and mislabel them `rejected_by="language"`
  instead of `"include_globs"`, reversing the fix the label is supposed to prescribe; **(c) casefold
  filenames**, which contradicts linguist's own semantics and git's, and would make `jenkinsfile`
  resolve to Groovy.
  Cost of getting it wrong is bounded and was measured before deciding: the only mixed-case extension
  on either corpus is NNG's `.MF`, and ctcm-api has none, so every pinned number in this plan is
  identical under all three readings. The rule is therefore free to adopt now and expensive to
  discover on a third corpus, which is the whole argument for writing it down at M0 rather than at
  the first bug report.
  Date/Author: 2026-09-02, M0 pre-flight blocker check.

- Decision: **The credential tier is tested before the `indexed` branch, so it outranks `indexed` as
  well as the three suppression tiers.** A file matching `include_globs` whose extension or stem is
  credential material is tiered `credential`, not `indexed`.
  Rationale: two binding sections of this plan gave opposite answers — the M1 `indexed` bullet said
  such a file falls through to `gap` with a `rejected_by` label, while `What must not happen` says the
  credential tier outranks every other non-indexed tier "precisely so a keystore can never be
  hidden". Measured before deciding: with `**/*.p12` in `include_globs`, `sec/app.p12` landed in
  `gap` with `rejected_by="language"` and `credential_files` was empty — the keystore buried in a
  276-row list rather than named in a four-row one. The trap is latent on both corpora (no default
  glob names a credential extension) and springs on exactly the action the `language` label exists to
  encourage, which is someone widening the allow-list. Rejected: **narrowing the wording** so
  "outranks" means only the suppression tiers, on the argument that adding `**/*.p12` to
  `include_globs` is a deliberate request to index it. Cheaper, and it keeps the `indexed` count
  strictly equal to what `discover_source_files` would open, but it makes the security guarantee
  conditional on a manifest nobody re-reads. Also rejected as scope: reporting the collision as a
  warning, which belongs in M2's output if it is wanted at all.
  Cost: nothing today — no pinned number on either corpus moves — and on a future repository whose
  allow-list names a credential extension, the `indexed` tier is one file smaller than `repo_files`
  per credential, which M3's reconciliation line must then explain alongside the first-party delta.
  Date/Author: 2026-09-02, maintainer decision during M1 review.

- Decision: **Close the coverage gap before Step 10 Phase 1 rebuilds the index, rather than after.**
  Eight patterns added to `ProjectConfig.include_globs` (`**/*.xml`, `.jsp`, `.properties`, `.css`,
  `.vm`, `.ent`, `.tld`, `.xmi`), seven language-registry entries, and a `_CHONKIE_SKIP_LANGUAGES`
  frozenset generalising the pre-existing `!= "xml"` guard.
  Rationale: the rebuild is one-shot and hours long, and an extraction run over the pre-widening
  index would have measured its own coverage against a denominator that excluded 19.60% of
  first-party bytes — reporting itself complete having never been shown the JSP layer. Doing it
  afterwards means doing the rebuild twice.
  Alternatives rejected: leaving the gap and noting it in the Step 10 report (the number that would
  be reported is the *wrong* number, not merely an incomplete one); deleting the index so the
  workflow falls back to grep (loses every benefit of Layer 0 to fix one of its defects).
  Cost: +4.4% index wall clock, +308 files, +482 chunks, +21 symbols. `repo_files` moves 1,229 →
  1,504 under the final configuration, which re-baselines the requirements plan and its runbook.
  Date/Author: 2026-09-08, maintainer decision.

- Decision: **`.properties` files are indexed despite carrying real cleartext credentials**, and the
  content-based credential gate that would make this safe is deferred to
  `pending/indexer-credential-gate.md`.
  Rationale: the maintainer's call, on the grounds that the analysis directory is laptop-local. The
  measured exposure is 15 files / 22 credential-shaped keys, `application-prod1.properties`
  included.
  **Caveat that survives the rationale:** Step 10 Phase 1 runs the Bedrock embedder
  (`provider: "api"`, `amazon.titan-embed-text-v2:0`), so these chunks *do* leave the laptop. Local
  storage is not the whole exposure.
  Alternatives rejected: dropping `**/*.properties` (leaves a non-zero residual gap); NNG-shaped
  path exclusions for the config directories (does not transfer to a second corpus); building the
  gate now (a milestone, and it blocks Phase 1).
  Date/Author: 2026-09-08, maintainer decision.

- Decision: **`discover_source_files` applies the walk's three provenance rules, rather than
  approximating them with path globs.** Extracted to `provenance.ThirdPartyClassifier`, which
  `gaps.walk_repository` now also uses; discovery resolves one from a new
  `ProjectConfig.domains_file` setting, defaulting to `None` (today's behavior exactly).
  Rationale: path globs cannot express the discriminator. Nine vendor `.tld` and two client `.tld`
  share one directory, and only the declared `<uri>` tells them apart — a `WEB-INF/tld/**` exclusion
  would delete `nngauthz.tld`, the access-control tag library Q27 exists to rescue. One
  implementation also means the index and the gap report can no longer disagree about which files
  are the vendor's, which a hand-authored exclusion list guarantees they eventually would.
  The setting names a *file* rather than inlining `vendored_globs`/`own_identities` into the
  manifest because `domains.json` already holds them and `/modernize-assess` already authors that
  file; duplicating them would create the second source of truth this decision exists to prevent.
  Resolution happens inside `discover_source_files` rather than at its call sites because there are
  four of them (the indexer, two CLI commands, the domain tagger) and
  `_reap_file_domains_to_discovered` deletes `file_domains` rows for undiscovered paths — a call
  site that disagreed would silently reap rows another had just written.
  Alternatives rejected: narrowing the include patterns to path shapes that miss the vendor copies
  (encodes NNG's directory layout, does not transfer); accepting the over-reach and recording it
  (re-imports content two mechanisms deliberately excluded).
  Cost: `.tld` drops from 13 discovered files to the 2 that are the client's; `.css` from 8 to 6.
  Date/Author: 2026-09-08, maintainer decision.

- Decision: **The 20 files the walk tiers as `first_party_excluded` stay out of the index, excluded
  by extension-scoped patterns rather than by directory.**
  Rationale: they are a bundled JAMon admin UI, EAR deployment descriptors, test Spring contexts and
  the gradle wrapper — not the business logic the extraction lenses mine. Directory-scoped
  exclusions were measured first and rejected: `jamon-web/**`, `ple-ear/**`,
  `ple-services-test/**` and `gradle/**` would have dropped **358 currently-indexed files** (332
  `.java`, 25 `.sql`) to suppress 20.
  Cost: exactly one file that is indexed today moves out —
  `ple-services-test/JavaSource/testconfig/applicationContext-test.xml`, which reached the index via
  the old `**/applicationContext*.xml` pattern and which the walk already tiers as first-party
  excluded. Deliberate, and it is the `-1` in the reconciliation `1,229 - 1 + 276 = 1,504`.
  Note this tier is *not* a walk/indexer contradiction in general: `domains.json`'s `exclude_globs`
  drive the `excluded` domain tag, and 383 files are already indexed-and-domain-excluded by design.
  These 20 are excluded outright because they are new arrivals nobody has argued for.
  Date/Author: 2026-09-08, maintainer decision.

- Decision: **Symbol-dead indexing of the JSP layer is accepted as the Step 10 substrate**, with the
  eventual re-keying filed as entry 9 of `pending/deferred-small-items.md`.
  Rationale: the lenses retrieve semantically and the coverage metric counts chunks, so retrieval
  coverage is what Step 10 actually consumes. Writing a JSP extractor first is a milestone, not a
  task, and it would block Phase 1 for its duration.
  Cost: when a JSP extractor eventually lands, citations into those files move from the file-level
  anchor floor to symbol anchors, changing `dedupe_key` tier 1 and re-keying every rule that cites
  JSP.
  Date/Author: 2026-09-08, maintainer decision.

- Decision: **`artifacts/gap-acceptance-manifest.json` now pins the historical 27 `include_globs`**,
  and M0–M2/M4 acceptance keeps reproducing against them while production config moves on. M3 is
  the deliberate exception and is re-pinned against the widened configuration.
  Rationale: without the pin the widening retroactively invalidates acceptance criteria that fix the
  gap tier at 276 files / 19.60%, leaving the detector reporting 0.00% on its own primary corpus.
  Alternatives rejected: re-pinning every milestone against the widened config (throws away the
  measurements that proved the detector works, and M1's whole value is that it reproduced two
  reference corpora exactly).
  Date/Author: 2026-09-08, maintainer decision.

## Outcomes & Retrospective

**M0 and M1 are shipped as of 2026-09-02; M2 is next.** Their details and test counts are in
`Progress` and are not restated here.

M1 confirmed the M0 prediction below almost exactly, and it is worth reading the two together. The
numbers were never in doubt — the walk reproduced both corpora on its first complete run, because the
probe had already settled them. Every defect the milestone actually surfaced was in the *types and
assertions this plan specified over those numbers*, which is what the paragraph below predicted: a
`DroppedFile` that could not express the raw headline the `Decision Log` defines, a `CheckResult.index`
rule that was wrong about which list it indexes, a credential tier two sections disagreed about, and
an `EACCES` path that crashed the command this plan promises never exits nonzero. None of the four is
reachable by re-reading prose, and none was caught by the three verification passes that preceded
implementation.

One method note worth keeping, because it is cheap and it worked. The walk and its unit tests were
written in parallel by two agents from this document alone, the test author forbidden from reading the
implementation. The tests passed against the implementation on the first run — which is weak evidence
the code is right and strong evidence *the specification is unambiguous*, since two independent
readings of it produced agreeing artifacts. The subsequent adversarial pass then found what neither
could: not disagreements between them, but places where they agreed with each other and with the plan,
and all three were wrong together. If M2 is built the same way, expect the same division of labour —
parallel readings catch ambiguity, and only an adversary reading against the corpora catches a settled
mistake.

The one thing worth carrying forward from building M0: the pre-flight pass that declared it unblocked
exercised every *external* precondition — the two-step GitHub fetch, the pinned commit's five volume
numbers, every pinned resolution, the three `tree_sitter` traps, `pyyaml` in the venv, packaging,
gitignore, both probe runs, the 408-test collection — and M0 still shipped with a defect in its
acceptance criteria, because the one thing that pass could not check was whether the criteria were
*satisfiable by the artifact it specified*. "833 languages, asserted from the vendored JSON" reads as
a measurement and is actually a claim about a file that did not exist yet; pruning drops six of the
833, so the assertion was unreachable by construction. Nothing short of writing the file would have
found it. Expect the same shape at M1–M3: the numbers are trustworthy because the probe produces
them, but the *types and assertions this plan specifies over them* have never been executed, and
that is where the next defect will be.

What the design phase produced, for comparison against the purpose above: a settled two-axis
exclusion model, a six-tier partition that reconciles to the walk total on two structurally
different corpora, and a committed probe that reproduces every acceptance number on demand. Two
design errors were caught only by running the rules against a second corpus (a 77.9% headline whose
largest finding was LegacyLift's own output) and by asking where an inherited exclusion list came
from (a glob that deleted 63 first-party files). Neither was found by re-reading prose. Keep that in
mind when validating the milestones below: run the probe, do not reason about it.

## Context and Orientation

### The tool, and where its files are

`legacylift-search` is a Python CLI in `tools/legacylift_search/`. Its source is
`tools/legacylift_search/src/legacylift_search/`, its tests are `tools/legacylift_search/tests/`, and
it is installed from `tools/legacylift_search/pyproject.toml`, which declares twelve runtime
dependencies. `pyyaml` is **not** one of them, and this plan keeps it that way.

The command indexes a repository into a SQLite database (`index.sqlite`) plus a Chroma vector store,
and exposes subcommands including `index`, `search`, `symbols`, `stats`, `coverage`, `domains` and
`tag-domains`. This plan adds one more, `gaps`.

Terms used throughout, defined once:

- **Manifest** — the JSON configuration file (`semantic-search.manifest.json` by convention) parsed
  into the `Manifest` pydantic model in `config.py`. `manifest.project` carries `include_globs`,
  `exclude_globs` and `max_file_bytes`.
- **Glob** — a path pattern matched with *gitignore* semantics by the `pathspec` library
  (`pathspec.PathSpec.from_lines("gitignore", patterns)`). `**`, `*`, `?` and character classes work;
  `{a,b}` brace expansion does **not**. Despite the dialect name, **no `.gitignore` file is ever
  read** anywhere in `legacylift_search`: `"gitignore"` at `discovery.py:51-52` names the syntax, not
  a source. This matters practically — `grep`/`ripgrep` *do* honour `.gitignore`, so any measurement
  taken with them sees a smaller tree than the indexer walks, and the two disagree on exactly the
  vendored and build content this plan is about. Use the probe, not `grep`.
- **Layer 0** — the index this tool builds: files, chunks, symbols, references, graph edges and
  facts. "Layer 0 cannot see it" means "there is no row for it in `index.sqlite`".
- **linguist** — GitHub's open-source language-classification data
  (`github-linguist/linguist`, MIT © GitHub), specifically `lib/linguist/languages.yml` (what
  language an extension or filename means, and whether that language is `programming`, `markup`,
  `data` or `prose`) and `lib/linguist/vendor.yml` (regular expressions matching third-party paths).
  This plan vendors a pruned, derived snapshot of both as JSON. It is used to **classify and rank**
  findings and **never** to filter them.
- **tree-sitter grammar** — a parser available from the `tree-sitter-language-pack` package already
  in the dependency list. Whether a grammar exists for an extension is the difference between "a
  parser could be written cheaply" and "a parser must be written from scratch".
- **Declared identity** — an origin a file states about itself: `.tld` files publish a `<uri>`,
  `.xsd` files a `targetNamespace`, `.dtd` files a PUBLIC identifier. Reading one is a fact lookup,
  not an inference.
- **Third-party** and **first-party excluded** — the two axes of exclusion. Third-party means "not
  this codebase, never was" (a vendored library, someone else's published schema): it is a **drop**,
  removed from the walk and from both sides of every ratio, because there is nothing for anyone to
  decide. First-party excluded means "ours, and we chose not to analyze it" (build config, IDE
  metadata, CI pipelines): it is a **named tier**, counted and totalled, because a human decision
  that shrinks the report must stay auditable.
- **Observed** and **predicted** mode — observed diffs the walk against the `repo_files` table and
  needs an index; predicted replays the manifest gates in-process and needs no database, so the check
  works before `index` has ever run.

### Why the gap exists — the mechanism, precisely

`discover_source_files` (`discovery.py:35-119`) walks the whole repository tree and applies gates in
this order:

1. `exclude_globs` — a denylist (`discovery.py:69-70`).
2. `include_globs` — an **allow-list** (`discovery.py:73-74`).
3. `detect_language` — returns `None` for an unrecognised extension (`discovery.py:77-79`).
4. `max_file_bytes`, default 2,000,000 (`discovery.py:88-89`).
5. A read error, swallowed silently (`discovery.py:96-98`).

The gate that produces the gap is **number two**, not number three. `ProjectConfig.include_globs`
(`config.py:21-53`) is an explicit allow-list of **27** patterns — 22 of the form `**/*.ext` and 5
path-shaped (`**/*-flow.xml`, `**/flows/**/*.xml`, `**/applicationContext*.xml`,
`**/spring/**/*.xml`, `**/config/**/*.xml`) — and every one of them maps to an extension that *is*
in `_EXTENSION_TO_KEY` (`languages.py:100-105`). **Under default configuration the
`detect_language is None` branch at `discovery.py:78` is unreachable.** Everything this plan finds
fails two steps earlier, at the allow-list.

That has a consequence for how the check must be written, and it is the single most common way to
get this wrong: **the check cannot walk "under the same include/exclude rules discovery applies."**
Applying an allow-list and then looking for what the allow-list rejected returns the empty set by
construction. The walk applies `exclude_globs` and then deliberately **drops** the `include_globs`
gate, reporting what survives.

A second, narrower gap sits inside the files that *are* indexed: a file can be opened, parsed, and
yield no symbols at all. That is one SQL query and it is a genuinely different failure, which is why
both checks ship together — shipping one alone makes the other look like it does not exist.

### The measurement that motivates the work

Walking the NNG application with the settled rules — manifest `exclude_globs` plus
`**/legacylift-docs/**`, third-party dropped, first-party exclusion applied as a tier to both sides
of the ratio — measured 2026-09-01:

        third-party DROPPED       72     762 KB    20730 lines
        indexed                  871    3301 KB    92232 lines
        gap                      276     805 KB    19637 lines
        first-party excl         482    2669 KB    66580 lines
        referenced content         0       0 KB        0 lines
        asset                     60    1345 KB     6873 lines
        credential                 4      41 KB      192 lines
        WALK TOTAL              1693    8161 KB   185514 lines

        HEADLINE  19.60% of bytes, 17.55% of lines

The gap tier by extension, byte-ordered, with the two classification columns the report carries:

        ext          files      KB   lines  linguist                       type         grammar
        .jsp           178     594   13117  Java Server Pages              programming  -
        .properties     42      81    1959  INI / Java Properties          data         properties
        .css             6      54    2901  CSS                            markup       css
        .ent             3      30     513  (unknown to linguist)          -            -
        .xml             8      25     541  XML                            data         xml
        .vm             35      18     509  (unknown to linguist)          -            -
        .tld             2       2      88  (unknown to linguist)          -            -
        .xmi             2       1       9  XML                            data         -

The headline answers a specific question: **of the code we said we intend to analyze, what fraction
can Layer 0 not see?** Both the numerator and the denominator have the first-party exclusion applied,
because a ratio whose two halves span different populations is not a measurement.

Four things this table settles by itself.

**`.jsp` is the finding** — 178 files and 74% of the gap by bytes, in a Spring Webflow application,
carrying display and validation logic, none of it indexed. It is known to linguist and has no
tree-sitter grammar, so the work item is "write an extractor or accept the gap", not "add a glob".

**A real finding does not have to be a large one.** `nngauthz.tld` is 1,630 bytes. It declares a
custom authorization tag bound to `com.nng.ple.web.tags.NngAuthorizeTag` — an access-control rule
applied across the JSP layer — and it survives into the gap only because reading its declared
identity overrode a `WEB-INF/tld/**` pattern that is otherwise correct. Nine of the eleven files in
that one flat directory are genuinely vendored; provenance is not a property of location.

**Lines re-rank the findings**, which is why both are counted. By bytes the order runs `.jsp`,
`.properties`, `.css`, `.ent`, `.xml`; by lines it runs `.jsp`, `.css`, `.properties`, `.xml`,
`.ent`. Two adjacent pairs swap — `.css` carries 2,901 lines in 54 KB against `.properties`' 1,959 in
81 KB, and `.xml` 541 against `.ent`'s 513. Ordering by one measure alone buries something, and a
file count alone buries both: 35 `.vm` templates outnumber every other non-JSP row and sit sixth by
bytes.

**Asset suppression is load-bearing, not tidiness.** The asset tier holds 1,345 KB against a whole
gap of 805 KB. Unsuppressed, the report's top finding on this corpus is a photograph.

Running the *same* rules against the second corpus, `repos/ctcm/ctcm-api`, is what makes them
trustworthy, and is where two of them originally broke:

        third-party DROPPED        5      93 KB     2139 lines
        indexed                 4715   11462 KB   295488 lines
        gap                      186     373 KB     9570 lines
        first-party excl           0       0 KB        0 lines
        referenced content        59   10083 KB    36918 lines
        asset                      0       0 KB        0 lines
        credential                 0       0 KB        0 lines
        WALK TOTAL              4960   21918 KB   341976 lines

        HEADLINE  3.15% of bytes, 3.14% of lines

This corpus is the mirror image of NNG — its asset tier is empty and its referenced-content tier
holds 59 files, where NNG's asset tier holds 60 and its referenced-content tier is empty. Neither
corpus alone would have produced both tiers. It is also the control on the both-sides arithmetic: it
has no `knowledge.sqlite`, therefore no first-party exclusion list, so its `repo_files` count and its
`indexed` tier must agree exactly (4,715 = 4,715, delta 0), where NNG's differ by 358.

Before the tier rules gained office formats and the `**/legacylift-docs/**` exclusion, this same
corpus reported a **77.9%** gap whose two largest findings were 103 `.json` files of LegacyLift's own
generated output and 57 Word templates counted as a million lines of "code". The general lesson
outranks the specific globs: **every rule was fitted to one corpus, and first contact with a second
broke two of them.** Acceptance criteria that pin one corpus cannot catch this, which is why the ones
below pin both.

### The two counting conventions, stated because both were once wrong here

**Kilobytes.** Each row is `round(bytes / 1024)`, and **the displayed total is the sum of the
displayed rows**, not the true total rounded separately. Rounding consistently is not enough on its
own: measured, per-row rounding happens to sum on NNG and does *not* on ctcm-api, where the displayed
rows come to 21,918 KB against a separately-rounded total of 21,917, because the fractional parts
accumulate past a half. Only summing the displayed rows makes "the tiers add up to the total" true by
construction, and that property is the one a reader checks with their eyes. Exact bytes go in
`--json`, where nothing is rounded.

**Lines.** `sum(1 for _ in open(path, "rb"))`, which differs from `wc -l` by one on a file with no
trailing newline. What matters is that one method is used on **both** sides of the ratio; the
acceptance numbers assume this one. Do not substitute an index-derived line count such as
`MAX(chunks.end_line)` — it is exact for only 1,173 of NNG's 1,229 indexed files, errs one-sided, and
is a *total*-lines figure where `scc`'s `Code` column is not, so mixing them misstates coverage by
roughly 28%.

### What must not happen

These are binding constraints, each with a measured cost behind it. The record's §5 carries the full
list and the evidence; the ones that will actually come up while implementing are:

- **Do not close the gap by indexing everything.** Adding extensions to `_EXTENSION_TO_KEY`, or globs
  to `include_globs`, without a parser produces `repo_files` rows with no symbols — moving files from
  check one to check two while inflating every coverage denominator. That looks like progress and is
  worse than the current state.
- **Do not use any allow-list as the gap oracle.** `scc`, linguist and `include_globs` share one
  failure mode: each silently omits what it does not recognise. Measured, `scc` 3.7.0 reports 1,541
  files against the walk's 1,765 and omits every `.tld`, `.vm`, `.ent` and dotfile — it would hide
  `nngauthz.tld` entirely. Only a walk that reports the unknown can find the unknown.
- **Do not let a denylist hide what an allow-list would have hidden.** The same rule cuts the other
  way: NNG's stored `domain_exclusions`, unioned into the report, deletes 11 of 13 `.tld`, all 14
  `.xsd` and all 4 `.dtd`.
- **Do not decide provenance from a path.** `WEB-INF/tld/` is 9/11 vendored; `xmlcatalog/` is 100%
  vendored; `com/nng/ple/service/external/` is 0% vendored and `vendor.yml`'s single pattern
  `(^|/)[Ee]xtern(als?)?/` claims all 63 files of it — the client's own external-*systems*
  integration layer, including `ContractsService.java` and `Contract.hbm.xml`. Three directories,
  three different truths. That is why `vendor.yml` contributes its 113 filename patterns and none of
  its 55 directory patterns.
- **Do not move a tier's membership rules into manifest `exclude_globs`.** The walk applies the
  manifest gate *before* it tiers anything, so a rule placed there deletes the tier instead of
  populating it. Measured: adding `**/*.png` and friends to the manifest takes NNG's asset tier from
  60 files to 0 and the walk total down with it. Suppression at the manifest gate means "never look
  at this"; tier membership means "we looked, and here is what it is." Only `**/legacylift-docs/**`
  belongs in the manifest, and that is M4's whole scope.
- **Do not suppress credential material as an asset.** Four files on NNG depend on this; the
  credential tier outranks every other non-indexed tier precisely so a keystore can never be hidden
  by an image glob.
- **Do not suppress a document that code resolves by name.** Fifty-seven of ctcm-api's 58 templates
  are bound to indexed C# by a constants class; the one that is *not* bound is the finding. Folding
  them into the asset bucket erases both facts at once.
- **Do not let the tiers overlap.** A reader who cannot add the columns to the walk total will not
  trust any of them.
- **Do not fold this into the semantic-typing pass** (`pending/fact-graph-decision.md` §5a.6 residue
  (b), specified at `pending/fact-graph-explanation.md` §9.8). That derives architectural roles over
  symbols that already exist; this is about source that produced no symbols at all.
- **Do not let it become a blocker on the requirements store.** `active/reqs-to-data-store.md`
  declares no dependency here.

## Plan of Work

Five milestones. M0 and M1 carry no user-visible surface at all, which keeps the riskiest part — the
shape of vendored third-party data — away from the CLI contract until it is proven.

### M0 — vendor the linguist data

Nothing in the repository can currently answer "what language is a `.tld` file?" or "does a
tree-sitter grammar exist for `.dtd`?". This milestone makes both answerable from data on disk, with
no new runtime dependency and no network access at run time.

The precedent is exact and should be followed rather than reinvented:
`src/legacylift_search/profiles/extractors.json` is a 12.5 KB derived JSON file carrying
`schema_version: 1`, loaded with `Path(__file__).resolve().parent / "profiles" / "extractors.json"`
(see `cli.py:1727-1729`) and already shipped by `[tool.setuptools.package-data]`
`legacylift_search = ["profiles/*.json"]` in `pyproject.toml`. A second file in the same directory
needs no packaging change.

Create `src/legacylift_search/profiles/linguist.json`, derived from upstream
`lib/linguist/languages.yml` and `lib/linguist/vendor.yml`, pruned to what this plan uses: an
extension→languages map, a filename→languages map, and `vendor.yml`'s regular expressions **split
into filename-shaped and directory-shaped lists** so that "the directory patterns are not adopted" is
an auditable property of the data rather than a comment in code. Carry the MIT attribution, the
upstream commit SHA and the fetch date inside the JSON.

**The split rule, stated because it exists nowhere else in prose.** A `vendor.yml` pattern is
*directory-shaped* when `pattern.rstrip("$").endswith("/")`, and *filename-shaped* otherwise; only
the filename-shaped list is adopted. That one line is the whole rule, it is what the probe
implements at `gap-detection-probe.py:174`, and on the pinned snapshot it splits 168 patterns into
113 adopted and 55 not. Getting it wrong changes the drop attribution on both corpora, so it is
asserted by volume in the M0 acceptance criteria.

Create `scripts/refresh_linguist.py` — a new `tools/legacylift_search/scripts/` directory — as the
**only** place `pyyaml` is imported. It runs on demand, never on a schedule and never at run time.

It fetches in **two steps, resolving the ref to a commit first and then pinning both downloads to
that commit**:

    GET https://api.github.com/repos/github-linguist/linguist/commits/<ref>          -> .sha
    GET https://raw.githubusercontent.com/github-linguist/linguist/<sha>/lib/linguist/languages.yml
    GET https://raw.githubusercontent.com/github-linguist/linguist/<sha>/lib/linguist/vendor.yml

with `--ref <sha>` able to reproduce an existing snapshot exactly. The first call is not optional and
not cosmetic: a `raw.githubusercontent.com/.../main/...` GET returns no commit SHA at all, so the
`upstream_commit` field this milestone requires is simply unobtainable from the one-step fetch the
probe uses. Both endpoints were verified reachable from this machine on 2026-09-02 (unauthenticated
`api.github.com` allows 60 requests an hour, which is ample for a script run by hand). Write the
**resolved** SHA into the JSON.

**The first run must pin the commit this plan measured, not `main`.** That commit is

        d5214e1612c858ba14bf98edeca57e1683276f1d   (committed 2026-09-01T09:40:55Z)

and it is the whole reason the volume assertions below are checkable. Re-verified on 2026-09-02 by
fetching both YAML files at that SHA and recounting: 833 languages, 1,486 extension keys, 419
filename keys, 168 `vendor.yml` regexes splitting 113 / 55, and every extension and filename
resolution the acceptance criteria pin. Run `refresh_linguist.py --ref
d5214e1612c858ba14bf98edeca57e1683276f1d` for the initial generation. `--ref main` is for a
*deliberate* later refresh, and it is expected to move the numbers — see the note under the M0
acceptance criteria.

The reason the SHA is written down here rather than left to the script is that without it the
milestone is unbuildable as specified: the first `--ref main` run fetches whatever upstream is on the
day, and if it has moved, the M0 test fails on its first execution with nothing to distinguish "the
refresh broke" from "upstream released". Pinning makes `833 / 1,486 / 419 / 113 / 55` properties of a
named commit rather than of a moving branch — which makes the test a genuine bad-refresh detector
instead of a tripwire that fires on the next linguist release.

Create `src/legacylift_search/linguist.py`, a small loader with no YAML dependency, and
`tests/test_linguist_profile.py`, which pins a handful of resolutions so that a bad refresh **fails**
instead of quietly emptying the report's classification columns. That test is the important half of
this milestone.

**Case, stated once so that every extension comparison in this feature agrees.** Extension keys
are written casefolded and looked up casefolded. This is not a preference: it is the behaviour of the
tool being measured — `languages.py:105` stores `ext.lower()` and `languages.py:117` looks up
`path.suffix.lower()`, so a gap walk that compared raw extensions would disagree with the very gate
it claims to model. The rule is lossless on the pinned snapshot: 15 of the 1,486 extensions are
mixed-case (`.PcbDoc`, `.Dsr`, `.JSON-tmLanguage`, ...) and not one collides with a distinct
lowercase sibling, so the key count is 1,486 either way. It is not academic either — NNG carries 14
`MANIFEST.MF` files, and `.MF` must reach the same "absent from linguist" answer as `.mf`. The rule
extends past M0 to every extension comparison M1 makes: the credential, asset and referenced-content
sets are written lowercase and matched against a casefolded extension, and `WalkedFile.extension`
stores the casefolded form so that `gap_by_extension` cannot split one extension across two rows.
**Filenames are the exception and are matched exactly** — that is linguist's own semantics and git's,
and `Jenkinsfile` is not `jenkinsfile`.

**The generated JSON must be byte-reproducible**, because "a later run with `--ref <that sha>`
regenerates a byte-identical file" is a property this milestone claims and nothing else enforces.
Write it with `json.dump(..., indent=2, sort_keys=True, ensure_ascii=False)`, open the output with
`encoding="utf-8"` and `newline="
"` — the default on Windows is CRLF, which alone would make two
runs on two machines differ — and end the file with a single trailing newline.

Two API traps must be covered by that test, because both fail silently:
`detect_language_from_extension` from `tree_sitter_language_pack` takes the extension **without** a
leading dot — `("dtd")` returns `"dtd"` and `(".dtd")` returns `None` — so getting it wrong empties
the whole grammar column with no error; and `has_language()` takes a *language name*, not an
extension, so the two are not interchangeable.

### M1 — the walk

This is the core of the feature and it touches no database, so it can be unit-tested against small
fixture trees.

Create `src/legacylift_search/gaps.py` with a `walk_repository` function that makes one pass over the
tree, reading each surviving file once for its line count and, where relevant, its declared identity.
Order of operations per file, exactly:

1. **Manifest gate.** If `exclude_globs` matches, the file is not part of the walk at all. It is not
   counted, not tiered, and not reported.
2. **Third-party provenance**, in strict precedence order. A file classified third-party is
   **dropped**: removed from the walk total and from both sides of every ratio, but recorded in
   `--json` together with the rule that dropped it, because 63 files vanishing without trace is the
   failure mode and 63 files listed under one named pattern is a five-second catch.
   1. **Declared identity**, for `.tld`, `.xsd` and `.dtd`, and only when at least one own-identity
      token is configured. Read at most the first 8,000 bytes and match `<uri>…</uri>`,
      `targetNamespace="…"` or `PUBLIC "…"`. If an identity is found, the file is third-party exactly
      when the identity contains **none** of the own-identity tokens (case-insensitive substring).
      This is authoritative in both directions and short-circuits the remaining rules: a file naming
      the client's own domain is first-party *even when a `vendored_globs` pattern claims it*.
   2. `vendor.yml`'s **filename** patterns from the M0 data — never its directory patterns. These
      are Python regexes matched with **`re.search` against the repo-relative POSIX path**, not
      against the basename: they are filename-*shaped*, not filename-*scoped*, so
      `(^|/)\.gitattributes$` must match `some/deep/dir/.gitattributes`. Reading "filename
      patterns" literally and matching `Path.name` compiles, runs, and silently changes the drop
      attribution on both corpora, which is why the M1 tests below pin a nested path explicitly.
      POSIX is not incidental to this rule and it is not local to it either — one repo-relative
      POSIX string per file is used by every gate, join and column in the feature; see the
      `relative_path` rule in `Interfaces and Dependencies` for the three places it is load-bearing.
   3. The `vendored_globs` list from `domains.json`.
   4. Otherwise first-party.
3. **Tiering**, mutually exclusive, in this precedence, so that the six tiers plus the drop bucket
   reconcile exactly to the tree:
   - **indexed** — is not a credential (that tier is tested first, above), matches `include_globs`
     **and** would survive the two gates that follow it in
     `discover_source_files`: `detect_language` returns a language, and the size is within
     `max_file_bytes`. A file that matches the allow-list but fails either of those is **not**
     indexed; it falls through to `gap` carrying `rejected_by="language"` or `rejected_by="size_cap"`
     respectively, which is the only way those labels are ever reachable. Under the default
     `include_globs` the `language` case cannot occur, because every default glob maps to an
     extension `_EXTENSION_TO_KEY` already knows; it becomes reachable the moment someone widens the
     allow-list, which is exactly when someone needs to be told.
     Separately, a file matching `include_globs` that *also* matches a first-party exclusion glob is
     **first-party excluded** rather than indexed. That branch is why the `indexed` tier is smaller
     than the `repo_files` table, and it is the whole content of the "applies to both sides of the
     ratio" decision.
     Measured on both corpora, neither the language nor the size-cap case fires: `indexed` comes to
     exactly `repo_files` minus the first-party exclusion (1,229 − 358 = 871 on NNG; 4,715 − 0 =
     4,715 on ctcm-api), so the reconciliation delta is fully explained and nothing is lost to the
     2 MB cap or to a read error. That is a property to re-check, not to assume, on any third corpus.
   - **credential** — extension in `.p12 .jks .keystore .pfx .pem`, or the filename or its stem is
     `ssTrustStore` or `cacerts` (case-insensitive). **This tier is tested first, ahead of the
     `indexed` branch above**, so a credential file is tiered `credential` however the allow-list is
     written; see the `Decision Log`. Here and in the two tiers below, the extension
     sets are lowercase literals matched against the casefolded extension, per the case rule in M0;
     the `include_globs` comparison above is the one place that stays case-sensitive, because
     `pathspec` is. Count and paths only; **no content is retained or emitted** — the file is read for
     its line count, which is what produces this tier's pinned 192-line figure, and nothing from it
     reaches `WalkResult`, the report or `--json`. `gaps` says only that they exist;
     `/modernize-assess`'s `SECRETS.local.md` step owns what to do about them.
   - **referenced content** — extension in `.docx .doc .xlsx .xls .pptx .ppt .pdf .zip`. Membership is
     by extension, *not* by whether a reference was found, so a zero-reference template stays in the
     tier and is reported as a finding rather than falling through to `gap` and being buried under
     genuinely unparsed source.
   - **asset** — extension in `.png .jpg .jpeg .gif .psd .ico .bmp .svg .woff .woff2 .ttf .eot`.
   - **first-party excluded** — matches a first-party exclusion glob, and carries `matched_glob`
     naming *which* one, because "excluded on purpose, and under which glob" is a table the report
     promises. Which glob that is, when more than one matches, is not a free choice: these globs are
     gitignore-dialect, where the **last** matching pattern decides and a `!`-prefixed pattern
     *un*-excludes. So `matched_glob` is the pattern whose match decided the outcome, not the first
     pattern that matched, and a file whose last match is a negation is **not** in this tier at all.
     Use `pathspec`'s `PathSpec.check_file`, which returns
     `CheckResult(file=..., include=True, index=1)` — `include` is the decision, and `index` is the
     deciding pattern's position in the **compiled** list, `spec.patterns`, which is *not* the list
     you passed: `from_lines` drops empty lines but keeps comments and whitespace-only lines as null
     patterns, so the two diverge from the first blank line onward. Read the text back off
     `spec.patterns[index].pattern`, never off your own input list (measured, with the transcript, in
     `Surprises & Discoveries`). `match_file` (a bool) cannot populate the field, which is why the
     probe has no `matched_glob`. Do **not** loop over per-pattern
     `PathSpec`s taking the first hit: it compiles, runs, and gets negation backwards, labelling
     files that a later `!` pattern rescued. `pathspec==1.1.1` is already pinned in `pyproject.toml`
     and `check_file` is present in it (verified 2026-09-02).
   - **gap** — everything else. Each gap file is labelled with the gate that rejected it:
     `include_globs` when it failed the allow-list, `language` when it passed the allow-list but
     `detect_language` returned `None`, `size_cap` when it passed both and exceeded
     `max_file_bytes`. The fixes differ — "edit the manifest" versus "write a parser" versus "raise
     the cap or accept it" — which is the entire reason the label exists. On both reference corpora
     every gap file carries `include_globs`; a row with any other label is new information.

Also in M1: add `vendored_globs: list[str] = []` and `own_identities: list[str] = []` to
`DomainsFile` (`domain_tagger.py:92-111`). Both are additive; pydantic ignores them today, so nothing
that reads `domains.json` changes behaviour.

### M2 — the `gaps` command

Add a `gaps` subcommand to `cli.py`, sitting beside `stats`, `coverage` and `domains`. It is not a
section of `stats` (already carrying an index table and a domain line) and not part of
`/modernize-preflight` (wrong lifecycle position — preflight runs before `index`, so the observed
mode would never be available there).

**What M1 already did for M2, field by field.** Sixteen of `GapReport`'s nineteen fields need no
database. `totals` is `walk.totals` verbatim, already complete and already carrying all six tiers
including the zeroed ones. `dropped` is `walk.dropped` verbatim, and it now carries `size_bytes` and
`line_count`, which is what makes both raw headlines computable without a second filesystem pass.
`gap_files` is `[f for f in walk.files if f.tier == "gap"]`, with `rejected_by` already populated.
`gap_by_extension` is that list grouped by `.extension`, with `linguist_languages` from
`classify_extension`, `tree_sitter_grammar` from `tree_sitter_grammar_for`, and `rejected_by` a
counter over the group. The referenced-content *rows* likewise come straight from the walk's tier.

Three fields are **derivations M2 must compute**, because nothing on `WalkResult` carries them:
`first_party_excluded_by_glob` (group the first-party tier by `matched_glob` into `TierTotals` —
verified to sum back exactly on both corpora), `credential_files` (the credential tier's paths), and
`walk_total` (summed over `totals`, displayed as the sum of the per-row roundings). `domains_source`
and `provenance_degraded` exist only at the CLI layer. **Only `symbolless_files`, `reconciliation` and
the reference counts need the store, and all three are M3.**

Output is a `rich` table following the `stats`/`coverage` house style, plus `--json` carrying
`schema_version: 1`. It leads with the headline in **both** raw and post-suppression form so the
suppression is visible rather than silently flattering, and reports **bytes and lines both** — when
those two headlines diverge violently, the remaining mass is a handful of huge binaries and that is a
suppression bug rather than a finding.

Truncation follows the discipline `SQLiteStore.coverage` already documents at `store.py:1085-1087`:
the producer returns everything, the caller truncates, and the totals stay exact over the full set.
Display default is the top 20 rows per tier with `--limit`; `--json` is always complete.

Both modes ship, with the mode named in the output. Observed is preferred when an index exists and is
strictly more truthful — it is the only mode that can see a file the indexer dropped on a **read
error**, which `discovery.py:96-98` swallows silently and which nothing about a file's path or size
predicts. Be precise about the other half: the `max_file_bytes` cap is *not* observed-only, because
M1's walk replays that gate itself and labels the file `rejected_by="size_cap"`. Predicted needs no database, so
the check is available before `index` has ever run. The two can legitimately disagree; the output
must say which produced the number. `--mode auto` (the default), `predicted` and `observed` behave
per the three-row table in `Interfaces and Dependencies`; that table, not this paragraph, is the
contract, and it exists because the obvious implementation — `cli_helpers.open_store_or_exit` —
exits 1 on a missing index and would contradict the rule below.

**No gate: the size of the gap never affects exit status**, on every path including "gap is 60% of
the tree". A threshold gate would fire on the reference corpus every single run, which teaches people
to pass the flag. The number travels instead of the block, which is M4. The **only** nonzero exit is
a usage error — `--mode observed` with no index, or an unreadable `--repo-root` — and it must name
the path it looked at.

`--domains` also carries the degraded-provenance guard specified in `Interfaces and Dependencies`:
when the resolved `domains.json` has neither `vendored_globs` nor `own_identities` the run warns on
stderr and sets `provenance_degraded: true`. NNG's live file is in exactly that state as of
2026-09-02 (re-measured: `exclude_globs` 45, both other keys absent), so this is the default path on
the reference corpus, not an edge case.

**Six traps for the CLI work, all measured 2026-09-02, none of them previously written down.**

- **A misspelled `--config` is silent, and it is the argument every acceptance number depends on.**
  `cli_helpers.py:86-89` loads the file if it exists and otherwise falls back to a bare `Manifest()`
  with no warning. A typo therefore runs against stock defaults, which lack `**/legacylift-docs/**`,
  and ctcm-api reports the pre-M4 **77.9% of bytes** with LegacyLift's own output as its largest
  finding — indistinguishable from a regression in the walk, and everything else about the run looks
  normal. Consider warning when `--config` names a path that does not exist.
- **`resolve_paths` prints a banner to stderr by default.** `print_banner: bool = True` emits
  `[legacylift-search] resolved index directory: <path>`. It is house behaviour (`stats` and
  `coverage` both do it) and cannot corrupt a stdout-parsing `--json` consumer, but it is an
  unrequested line nobody expects; `print_banner=False` is available.
- **`--limit` truncation goes in the command body, never in the producer.** `coverage` is the model:
  `listed = result.uncovered_chunks[: max(limit, 0)]` (`cli.py:1599`) — note `max(limit, 0)`, so a
  negative limit means "none" rather than a reverse slice. The acceptance check that `--limit 3
  --json` and `--limit 20 --json` return identical row counts is satisfiable only if the JSON branch
  never sees `limit` at all.
- **`coverage` is the house-style model to copy, not `stats`.** It is the only existing command with
  both `--limit` and `--json`: a one-line summary sentence before the table (`cli.py:1599-1657`),
  `overflow="fold"` on every column, `console.print_json(json.dumps(payload))`, and — the part that
  matters here — its warning routed through a fresh `Console(stderr=True)` in JSON mode
  (`cli.py:1619`) precisely so stdout stays parseable. That is the pattern the degraded-provenance
  warning must follow. `domains` supplies the numeric convention, `add_column("Files",
  justify="right")`. Note that **no existing `--json` payload in this CLI carries `schema_version`**,
  so `gaps` is the first and has no precedent to copy for its placement.
- **`load_domains_json` raises two different exception types, and `schema_version` is required.**
  `domain_tagger.py:125-142` raises `FileNotFoundError` for a missing file and wraps both malformed
  JSON and schema failures as `ValueError`. `DomainsFile.schema_version` has no default, so a
  hand-written `domains.json` that omits it is a hard `ValueError`, not a degraded run. `--domains
  none` must be intercepted as a literal string *before* this call.
- **`open_store_or_exit` is unusable for a second reason this plan did not record**: besides exiting
  1 on a missing index, it returns a plain read/write `SQLiteStore(sqlite_path)` (`cli_helpers.py:138`)
  with no `read_only` keyword, so even after M3 adds that keyword the helper would not pass it.

**Two questions the pinned runs do not answer, so decide them deliberately rather than by accident.**
First, how `--own-identity` combines with `domains.json`'s `own_identities` is undefined — union,
flag-wins and file-wins all reproduce the pinned numbers, because the Step 3 NNG run supplies
`nngco.com` by both routes and duplicate tokens are harmless. Second, `provenance_degraded` is
defined only over "the resolved file carries neither key", which says nothing about the **no file at
all** case — and that is exactly the pinned ctcm-api run, whose `resolve_analysis_dir` returns `None`
so no default `domains.json` can even be formed. Whether that run reports `true` or `false` is
currently undetermined by the wording.

### M3 — the index-backed checks

Two additions that both need the SQLite connection, which is why they are one milestone. The
connection is opened **read-only**, via the additive `SQLiteStore(path, read_only=True)` keyword
described in `Interfaces and Dependencies`; `gaps` never calls `migrate()`.

**Check two — indexed but empty.** `repo_files LEFT JOIN symbols` grouped by file, having zero
symbols and `size_bytes >= --min-bytes` (default 2048). The default is a corpus-specific judgment,
so it is exposed rather than welded in. Rows are then filtered through the same first-party,
`vendored_globs` and `vendor.yml` rules the walk uses; without that filter the check reports files
the walk has already accounted for.

**Check two needs a FOURTH state, added 2026-09-08.** Before the coverage widening every language in
the registry had an extractor, so "indexed, and zero symbols" could only mean *the extractor found
nothing, which is suspicious*. Seven of the eight widened languages have no extractor at all, so the
same query now also returns *no extractor exists for this language, which is expected* — and those
outnumber the real findings by a wide margin. Reporting them together makes the check useless: raw
zero-symbol files go 36 → 331, and at `--min-bytes 2048` they go 8 → 143. **The two states must be
separated in the output, not merged and not filtered away** — "expected to have no symbols" is
itself the finding that motivates writing an extractor.

The discriminator is `SymbolExtractor.has_extractor(language_key)`, added for this purpose. Read its
docstring before reimplementing it: it is `language_key == "xml" or language_key in
extractors.json`'s profiles, and **both clauses matter** — `xml` is dispatched to the framework-aware
`xml_extractor` above the profile lookup and has no profile of its own, so profile-presence alone
misfiles the one widened language that does produce symbols. It is **not**
`LanguageSpec.supports_tree_sitter`, which is dead code and in any case answers a different question:
`.css` and `.properties` have tree-sitter grammars that load fine and still yield nothing, because
`extract` never reaches a parser without a profile.

**Re-pinned acceptance, NNG, under the settled post-widening configuration** (was 8 raw / 5 after
exclusion, against the pre-widening 27 globs):

| | value |
|---|---|
| discovered files | 1,504 |
| of which have an extractor | 1,236 |
| **expected to have no symbols** (no extractor) | **268** — `.jsp` 178, `.properties` 42, `.vm` 35, `.css` 6, `.ent` 3, `.xmi` 2, `.tld` 2 |
| same, at `--min-bytes 2048` | 135 |

ctcm-api is **unmeasured** against the widened configuration and must be measured before M3 is
accepted; its pre-widening value was 0 raw findings, which is what made it the useful control.

**The reconciliation line, re-pinned.** It previously read `repo_files` 1,229 versus `indexed` 871, a
358-file delta that was entirely first-party exclusion. Under the settled configuration
`discover_source_files` returns **1,504**, reconciling as `1,229 - 1 + 276`: the whole 276-file gap
closes, and the `-1` is
`ple-services-test/JavaSource/testconfig/applicationContext-test.xml`, deliberately excluded (see the
Decision Log). The walk's own `indexed` tier reads 1,120 against the same configuration, because
`domains.json`'s `exclude_globs` move 489 files into `first_party_excluded` on the walk side while
the indexer still indexes them and tags them `domain='excluded'`. **That is by design, not a
discrepancy** — 383 files were already indexed-and-domain-excluded before this change — and the
report must say so rather than leave someone to diff the two and file a bug.

**The referenced-content reference count.** For each file in the referenced-content tier, count the
indexed evidence that resolves to it *by name* — chunks whose text contains the filename, and
`symbol_refs` rows naming it — and flag the ones whose count is zero. This reads no document
contents and adds no parser: the file becomes a counted fact sitting on one end of a real
code→content edge the index cannot otherwise see. On ctcm-api, 57 of the 58 templates under
`CTCM.API.DocumentService/Templates/` are bound to indexed C# by a constants class
(`CTCM.API.Shared/Dto/Document/TemplateNames.cs`, which carries all 57 as
`public const string BenefitAddendum = "BenefitAddendum.docx";`), and `MergeClassAttribute.cs:12`
states the contract outright — *"Required for finding proper template. Must be titled exactly like
file."* Exactly one file trips the zero-reference flag.

**Also in M3: the reconciliation line**, because it is the thing an implementer will get wrong. On
NNG, `repo_files` holds 1,229 rows while the `indexed` tier holds 871. The 358-file difference is the
first-party exclusion, and the report must **state** it rather than leave someone to diff the two and
file a bug. Observed mode's walk-versus-`repo_files` diff must account for the same 358 instead of
reporting them as discrepancies. On ctcm-api the delta is 0, which is what makes it the useful check
on this logic.

### M4 — make the number travel

Two small changes and no new code path.

Add `**/legacylift-docs/**` to `ProjectConfig.exclude_globs`, widening the existing
`**/legacylift-docs/index/**`. Verified safe on both corpora: the `indexed` tier is unchanged at 871
(NNG) and 4,715 (ctcm-api), because no file matching `include_globs` lives under that directory.
Without it, the gap report's largest finding on ctcm-api is LegacyLift's own generated output.

Wire the figure into `/modernize-assess` by editing
`.claude/skills/code-modernization/commands/modernize-assess.md` — the only skill file this plan
touches — so that Step 6 shells out to `legacylift-search gaps --json` and quotes the headline inline
in `ASSESSMENT.md`, at the point where coverage claims are actually made. **No new artifact is
written.** Writing `analysis/$1/GAPS.json` was considered and rejected: the figure is one cheap walk,
so persisting it buys a `/modernize-status` inventory row at the cost of a staleness liability.
`ARCHITECTURE.mmd` earns persistence because it is an expensive rendering; this does not.

That file already carries a CapTech attribution line dated 2026-09-01 (added when
`/modernize-assess` was split into two glob lists). Per `CLAUDE.md`, **overwrite** it — keep only the
latest modification, never accumulate a history.

## Concrete Steps

### Environment — read this first, it will save you a wasted run

Use the venv interpreter directly. The `legacylift-search` shim on `PATH` is broken.

    C:/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe

**If you are working in a git worktree, the venv is not in it.** The virtual environment exists only
in the main checkout, and its editable install resolves `legacylift_search` to the main checkout's
`src/` — a different branch. Tests will run and will not test your code. Always point `PYTHONPATH` at
the source tree you are editing:

    cd <your checkout>/tools/legacylift_search
    PYTHONPATH="$PWD/src" \
      C:/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe \
      -m pytest

Confirm it took effect before trusting a run:

    PYTHONPATH="$PWD/src" <venv python> -c "import legacylift_search; print(legacylift_search.__file__)"

and check the path printed is the checkout you are editing.

**Do not add `-q` to the pytest commands below.** `pyproject.toml` already sets
`addopts = "-q"`, so passing it again makes `-qq`, and at that level pytest prints the progress dots
and **no summary line at all** — no `N passed`, no collected count. Since every milestone here is
verified against a test count, the one flag that looks like tidiness silently removes the number you
came for, leaving you to count dots. Verified 2026-09-02: `-m pytest -q` on the M0 file prints only
dots; `-m pytest` prints `18 passed`. The commands below are written without it deliberately.

**The corpora are not in a worktree either.** They live in the main checkout:

    <main>/repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app
    <main>/repos/ctcm/ctcm-api

with indexes at

    <main>/repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app/index/code-search/index.sqlite
    <main>/repos/ctcm/ctcm-api/legacylift-docs/index/code-search/index.sqlite

`ctcm-api` has **no `knowledge.sqlite`** — its `legacylift-docs/knowledge/` is empty. That is not a
defect: it is what makes ctcm-api the control corpus for anything involving first-party exclusions.

**It does not, however, exercise predicted mode, and an earlier revision of this plan said it did.**
Predicted versus observed turns on `index.sqlite`, not on `knowledge.sqlite`, and ctcm-api's
`index.sqlite` exists at the path `resolve_index_dir` computes for it with no flags — measured
2026-09-02: `resolve_analysis_dir` returns `None` (its parent directory is not named `legacy`, so the
convention does not apply), resolution therefore falls through to
`<repo_root>/legacylift-docs/index/code-search`, and the file is there with 4,715 `repo_files` rows.
A bare `gaps --repo-root .../ctcm-api` runs **observed**. The only way either corpus reaches
predicted mode is the deliberate one the M2 acceptance criteria use: `--mode predicted`, or
`--index-dir` pointed at a directory that does not exist.

### Step 0 — establish the baseline, and confirm the probe

Run the suite and confirm it still matches the recorded baseline:

    cd <checkout>/tools/legacylift_search
    PYTHONPATH="$PWD/src" <venv python> -m pytest

On `feature/layer0-extraction-gap-detection` this was **408 collected, 408 passing** before M0, **426**
after it, and **456 after M1** (measured 2026-09-02, between 4 and 10 minutes depending on the
machine — the run takes minutes because the embedding tests load a model). Those three numbers are
history, not your target: the branch merged into `feature/reqs-to-data-store` on 2026-09-03, which brought that branch's ~750 tests with it.
**Use 1,250 as the floor** (measured 2026-09-08, exit 0, 6m21s) — it is the
number to beat when starting M2, and 456 will now look like a catastrophic regression rather than a
pass. The contributions remain additive: 1,159 + 18 + 28 + 2 = 1,207 at the 2026-09-03 merge, then
+43 from the 2026-09-08 coverage widening (`test_coverage_config.py` 28, `test_provenance.py` 14,
and one sentinel test in `test_gaps_walk.py`) = **1,250**. If
you get a
different count, find out why before starting — the most likely cause by far is the `PYTHONPATH`
trap above, which silently tests a different branch's source. If the suite is red for a reason
unrelated to this plan, record the count and the failures in `Progress` and carry on; do not fix
another plan's defects here.

Then reproduce both corpora. Each run prints its expected result on the second line, so a
disagreement is visible immediately rather than argued:

    cd <checkout>
    <venv python> docs/exec-plans/active/artifacts/gap-detection-probe.py nng \
        --repo C:/Users/dnorton/captechdev/legacylift-ai
    <venv python> docs/exec-plans/active/artifacts/gap-detection-probe.py ctcm \
        --repo C:/Users/dnorton/captechdev/legacylift-ai

`--repo` is required from a worktree. `--vendor <path to vendor.yml>` is optional; without it the
probe fetches from GitHub. Expected head of the NNG run:

        === nng ===
          expected: 871 indexed / 276 gap / 482 first-party / 60 asset / 4 credential, walk 1693, ...

          third-party DROPPED       72     762 KB    20730 lines
          indexed                  871    3301 KB    92232 lines
          gap                      276     805 KB    19637 lines
          ...
          HEADLINE  19.60% of bytes, 17.55% of lines

If those do not reproduce, stop and find out why before writing code. Everything below is pinned to
them.

### Step 1 — M0

    cd <checkout>/tools/legacylift_search
    mkdir scripts
    # author scripts/refresh_linguist.py, then:
    <venv python> scripts/refresh_linguist.py \
        --ref d5214e1612c858ba14bf98edeca57e1683276f1d \
        --out src/legacylift_search/profiles/linguist.json

**Pass that SHA, not `main`.** It is the commit every M0 acceptance number was measured against
(2026-09-01T09:40:55Z, re-verified 2026-09-02), so the run reproduces `833 / 1,486 / 419 / 113 / 55`
and the test passes on its first execution. `--ref main` on some later day fetches a different
snapshot and the test will fail with no way to tell a broken refresh from an upstream release.

`--ref` accepts a branch or a 40-hex SHA. The script resolves it through `api.github.com` and then
downloads both YAML files pinned at the resolved commit, so a later run with `--ref <that sha>`
regenerates a byte-identical file. Defaulting `--ref` to `main` is fine — the default is for the
deliberate-refresh case; the first run passes the SHA explicitly.

The script needs `pyyaml`, which is deliberately absent from the runtime dependency list; if the venv
does not have it, `pip install pyyaml` there. It must not be added to `pyproject.toml`.

Expected shape of the generated file (`sort_keys=True` means the keys land alphabetically on disk;
they are listed logically here):

        {
          "schema_version": 1,
          "attribution": "Derived from github/linguist languages.yml and vendor.yml. MIT (c) GitHub, Inc.",
          "upstream_commit": "<40-hex sha, resolved from --ref, NOT the literal branch name>",
          "fetched_at": "2026-09-02",
          "upstream_language_count": 833,
          "extensions": {".jsp": [{"name": "Java Server Pages", "type": "programming", "group": "Java"}], ...},
          "filenames": {"Jenkinsfile": [{"name": "Groovy", "type": "programming", "group": null}], ...},
          "vendor_filename_patterns": [...],
          "vendor_directory_patterns": [...]
        }

Run the generator a second time to a scratch path and diff the two outputs before committing. It
takes ten seconds and it is the only check that the byte-reproducibility claim above is true; a CRLF
default or an unsorted dict makes every future refresh an unreadable diff, and the failure is
invisible until then.

**And the writer is only half of it.** This repository is `core.autocrlf=true`, so git will convert
the file back to CRLF on checkout unless an attribute stops it — which is why
`.gitattributes` at the repository root pins this one path to `eol=lf`. Do not delete that line, and
if you move or rename the profile, move the line with it. `Surprises & Discoveries` has the
measurement.

Then run the new test:

    PYTHONPATH="$PWD/src" <venv python> -m pytest tests/test_linguist_profile.py

### Step 2 — M1

Author `src/legacylift_search/gaps.py` and `tests/test_gaps_walk.py`. The unit tests build small
temporary trees and assert tier membership directly; they do not need a corpus. Cover at minimum:
manifest exclusion beats everything; a credential file with an asset-looking name lands in
`credential`; a `.docx` lands in `referenced content` whether or not anything references it; a file
matching both `include_globs` and a first-party exclusion lands in `first-party excluded`, not
`indexed`; a `.tld` declaring the client's own domain survives a `vendored_globs` pattern that claims
it; the same `.tld` with no own-identity token configured is *not* dropped by the identity rule; a
file matching `include_globs` whose extension has no language lands in `gap` with
`rejected_by="language"` rather than in `indexed`; a file matching `include_globs` that exceeds
`max_file_bytes` lands in `gap` with `rejected_by="size_cap"`; and the tiers plus the drop bucket sum
to the file count of the tree minus the manifest exclusions.

Four more that exist because the specification changed under review, and each one fails silently
rather than loudly if it is skipped:

- Every path the walk emits is POSIX. Assert it on a fixture nested at least two directories deep,
  which is the only depth at which the bug is visible: `"\\" not in f.relative_path` for every
  `WalkedFile`, `DroppedFile` and `rescued_by_identity` entry, and one positive check that the
  expected `a/b/c.jsp` string is present verbatim. This test does nothing on Linux and is the whole
  guard on Windows, where `Path.relative_to` yields backslashes and every downstream gate then
  misses — see the `relative_path` rule in `Interfaces and Dependencies`.

- A `vendor.yml` filename pattern matches on the **path**, not the basename. Pin it with a case a
  basename match cannot satisfy: `src/CTCM.API/.gitignore` is third-party by `vendor.yml`, while
  `src/gitignore-notes.md` is not.
- A first-party excluded file carries `matched_glob` naming the pattern that claimed it, and
  `first_party_excluded_by_glob` sums back to the `first-party excluded` tier totals exactly.
- `walk_repository` is called with no keyword arguments at all on one fixture and mutates none of
  its defaults, so a second call on a different tree returns an unaffected result. The signature
  takes `Sequence[str] = ()` rather than `list[str] = []` for this reason.

    PYTHONPATH="$PWD/src" <venv python> -m pytest tests/test_gaps_walk.py

### Step 3 — M2, and the manifest the acceptance runs need

The pinned numbers assume `**/legacylift-docs/**` is excluded, which is not a default until M4, and
they assume NNG's Q27-split glob lists, which its live `domains.json` still does not carry. **Both
inputs are committed — do not rebuild them by hand:**

        docs/exec-plans/active/artifacts/gap-acceptance-manifest.json      config.py's 32 defaults + **/legacylift-docs/**
        docs/exec-plans/active/artifacts/gap-acceptance-domains-nng.json   NNG's 10 vendored / 33 first-party / own_identities

The second is the Q27 re-classification, identical to the probe's `NNG_VENDORED` and
`NNG_FIRSTPARTY` constants (`gap-detection-probe.py:102-124`) — see the `Surprises & Discoveries`
entry on why those two lists come to 43 rather than the live file's 45. Pass them as `--config` and
`--domains`. When `/modernize-assess` is next run on NNG with the two-list prompt, the domains file
comes from the real `domains.json` instead and these constants become its expected output.

Two committed scripts run the acceptance for you, both taking `nng` or `ctcm` and resolving their
fixtures as siblings:

        artifacts/gap-acceptance-walk.py     the tier table and both headlines, in the probe's
                                             exact format so the two can be diffed line for line
        artifacts/gap-acceptance-labels.py   what the probe cannot check -- drop attribution, the
                                             two identity rescues, gap-by-extension, `rejected_by`,
                                             `matched_glob`, and the POSIX guarantee

Run them from `tools/legacylift_search` with `PYTHONPATH="$PWD/src"`, exactly as for pytest. When `/modernize-assess` is next run on NNG with the two-list prompt, these
come from the real `domains.json` instead and the probe constants become its expected output.

    cd <checkout>
    <venv python> -m legacylift_search.cli gaps \
        --repo-root <main>/repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app \
        --config <scratch>/gaps-manifest.json \
        --domains <scratch>/gaps-domains.json \
        --own-identity nngco.com

### Step 4 — M3

Same invocation; observed mode now engages because the NNG index exists. Add `--min-bytes` to
exercise the floor, and run the ctcm-api corpus to confirm check two still returns zero — the
negative result is what proves the check discriminates rather than always firing.

### Step 5 — M4

Edit `config.py` to add the glob, then **re-run both acceptance suites with the acceptance manifest
removed** and confirm every number is identical. That equality is M4's acceptance criterion. Then
edit `.claude/skills/code-modernization/commands/modernize-assess.md`, overwriting its existing
`Modified by CapTech on 2026-09-01: …` line rather than appending a second one.

## Validation and Acceptance

Acceptance is pinned to exact numbers on **both** corpora. A structural assertion such as "reports a
non-empty gap" would sail past a regression in the exclusion rules, and an NNG-only assertion sails
past everything the second corpus found. Pin both.

### M0

`tests/test_linguist_profile.py` passes and asserts, from the vendored JSON:

- Volumes: 833 languages (as `upstream_language_count`) **and 827 distinct language names in the two
  maps**, 1,486 extension keys, 419 filename keys, 168 `vendor.yml` regexes split **113 filename / 55
  directory** by the `rstrip("$").endswith("/")` rule, with each split list asserted to obey the rule
  it was split by. These are properties of commit `d5214e1612c858ba14bf98edeca57e1683276f1d`,
  re-measured at that SHA on 2026-09-02 — which is why Step 1 pins it rather than fetching `main`.
  The 833/827 pair is not redundant: it is what separates "upstream changed" from "the inversion
  broke", and the gap between the two numbers is explained in `Surprises & Discoveries`.
- The vendored JSON's `upstream_commit` is 40 hex characters, is not a branch name, and on the
  initial generation is exactly `d5214e1612c858ba14bf98edeca57e1683276f1d`.
- Extension resolutions: `.jsp` → `Java Server Pages` / `programming`; `.xsd` and `.xml` → `XML` /
  `data`; `.css` → `CSS` / `markup`; `.properties` → `INI` and `Java Properties`, both `data`;
  `.gradle` → `Gradle` / `data`; `.htm` → `HTML` / `markup`; `.txt` → `Adblock Filter List`, `Text`,
  `Vim Help File`.
- Absences, which matter as much as presences: `.tld`, `.dtd`, `.ent`, `.vm`, `.mf`, `.png` and
  `.docx` resolve to nothing.
- Filename resolutions: `Jenkinsfile` → `Groovy` / `programming`; `.project` and `.classpath` →
  `XML` / `data`; `.gitignore` → `Ignore List` / `data`; `.keep` absent.
- Case handling, both directions: `classify_extension(profile, ".JSP")` resolves exactly as `".jsp"`
  does and `(".MF")` resolves to nothing exactly as `(".mf")` does — NNG's 14 `MANIFEST.MF` files are
  why this is asserted rather than assumed — while `classify_filename(profile, "jenkinsfile")` is
  **empty** and `"Jenkinsfile"` is not.
- Every language entry the profile carries has a non-null `type`, so the report's type column can
  never be blank for a language linguist knows. (Upstream, 0 of 833 omit it; the assertion runs over
  the 827 the maps carry, which is the set the report can actually reach.)
- The vendored file is written deterministically: its top-level keys are sorted, it contains no
  carriage returns, and it ends with exactly one newline. Together with the pinned commit this is
  what makes a re-run diffable instead of merely re-fetchable.
- The tree-sitter side, asserted against `tree_sitter_language_pack` directly:
  `detect_language_from_extension("dtd") == "dtd"`, `detect_language_from_extension(".dtd") is None`
  (the leading-dot trap), `has_language("css") is True`, `has_language("jsp") is False`, and
  `has_language("dtd") is True` — the last two together are what make the two classification columns
  complementary rather than redundant.

Run before and after: the test file does not exist before this milestone and passes after. The
existing suite count must be unchanged apart from the new file's tests. **Measured 2026-09-02:
408 → 426, exit 0**, which is the 18 new tests and nothing else.

One expectation about this test's future, so that nobody deletes it the first time it goes red: a
**deliberate** `refresh_linguist.py` run against a newer `--ref` is *expected* to move the volume
numbers, and updating them — here, and the SHA in the M0 narrative and Step 1 — is part of that
commit. The test's job is to catch a refresh that broke, not a refresh that happened. It can do that
job only because the JSON is pinned to a commit — fetched from a moving `main`, every upstream
release would look like a failure, which is the state this plan was in until 2026-09-02.

### M1

`tests/test_gaps_walk.py` passes, and the walk reproduces the probe on both corpora.

*NNG*, with `--own-identity nngco.com` and the two authored lists:

        third-party DROPPED       72     762 KB    20730 lines
        indexed                  871    3301 KB    92232 lines
        gap                      276     805 KB    19637 lines
        first-party excl         482    2669 KB    66580 lines
        referenced content         0       0 KB        0 lines
        asset                     60    1345 KB     6873 lines
        credential                 4      41 KB      192 lines
        WALK TOTAL              1693    8161 KB   185514 lines

        HEADLINE  19.60% of bytes, 17.55% of lines

The KB column must sum to the walk total exactly (3301 + 805 + 2669 + 0 + 1345 + 41 = 8161). Exact
walk bytes are 8,357,242, whose separate rounding is also 8161 here — the case that distinguishes the
two conventions is ctcm-api below.

Gap by extension, top rows: `.jsp` 178 / 594 KB / 13,117 lines; `.properties` 42 / 81 / 1,959;
`.css` 6 / 54 / 2,901; `.ent` 3 / 30 / 513; `.xml` 8 / 25 / 541; `.vm` 35 / 18 / 509; `.tld` 2 / 2 /
88; `.xmi` 2 / 1 / 9.

The third-party drops must attribute as `declared-identity` 29, `vendor.yml` 12, `vendored_globs` 31,
and the two files rescued by declared identity from the `WEB-INF/tld/**` pattern must be exactly
`ple-web/src/main/webapp/WEB-INF/tld/naesb.tld` and `.../nngauthz.tld` — nothing else.

*ctcm-api*, with `--own-identity ctcm` and no authored lists:

        third-party DROPPED        5      93 KB     2139 lines
        indexed                 4715   11462 KB   295488 lines
        gap                      186     373 KB     9570 lines
        first-party excl           0       0 KB        0 lines
        referenced content        59   10083 KB    36918 lines
        asset                      0       0 KB        0 lines
        credential                 0       0 KB        0 lines
        WALK TOTAL              4960   21918 KB   341976 lines

        HEADLINE  3.15% of bytes, 3.14% of lines

**This corpus is the counting-convention test.** The displayed rows sum to 21,918 KB; the exact walk
total is 22,442,956 bytes, which rounds separately to 21,917. The displayed total must be 21,918. If
your implementation prints 21,917, it is rounding the total independently and the column a reader
adds up does not add up.

Its five third-party drops must be exactly three by declared identity — the `iaiabc.org` EDI schemas,
two under `CTCM.API.EdiService/Xml/xsd/` and one under `CTCM.API.EdiService.Tests/Xml/xsd/` — plus
two by `vendor.yml` filename pattern, `.gitignore` and `.gitattributes`. Note that this corpus has no
`vendored_globs` at all, so without the declared-identity rule those three schemas become gap
findings and the headline moves; that is the measured cost of omitting `--own-identity`, and it is
the reason the flag is passed here even though no ctcm-api file names its own token.

**Exact bytes and lines, both corpora**, measured against the shipped walk 2026-09-02 and recorded
here so that every rounding above is checkable without re-running anything:

        NNG                     files          bytes       lines   round(b/1024)
          indexed                 871      3,380,666      92,232      3301
          credential                4         42,218         192        41
          referenced_content        0              0           0         0
          asset                    60      1,377,156       6,873      1345
          first_party_excluded    482      2,733,248      66,580      2669
          gap                     276        823,954      19,637       805
          WALK TOTAL             1693      8,357,242     185,514      8161   (round(total) also 8161)
          DROPPED                  72        780,580      20,730       762   (per-file sum: 755)

        ctcm-api                files          bytes       lines   round(b/1024)
          indexed                4715     11,736,628     295,488     11462
          referenced_content       59     10,324,590      36,918     10083
          gap                     186        381,738       9,570       373
          credential / asset / first-party    all zero
          WALK TOTAL             4960     22,442,956     341,976     21918   (round(total): 21917)
          DROPPED                   5         95,132       2,139        93   (per-file sum: 94)

Both `DROPPED` rows are the case that settles the rounding rule *within* a row: round the row's total
once. The pinned 762 and 93 come from `round(total/1024)`; summing per-file roundings gives 755 and
94, and both are wrong.

Headlines to four decimals, so the two-decimal figures above are checkable: NNG **19.5964%** of bytes
(823,954 / 4,204,620) and **17.5536%** of lines; raw **63.0036%** and **55.2802%**. ctcm-api
**3.1501%** of bytes (381,738 / 12,118,366) and **3.1371%** of lines; raw **47.9254%** and
**14.1310%**.

*ctcm-api's complete gap-by-extension table* — 14 rows, not the 8 quoted earlier in this plan, and
the tail matters because M2 displays it:

        .tpl 23 / 67,346 / 2,055      .xml 7 / 56,039 / 893       .html 32 / 50,748 / 1,646
        .json 45 / 43,049 / 1,368     .sln 1 / 40,356 / 501       (none) 22 / 36,769 / 967
        .csproj 34 / 33,651 / 882     .md 2 / 25,495 / 565        .ps1 6 / 9,911 / 216
        .sh 7 / 8,446 / 188           .yaml 1 / 7,828 / 245       .liquid 3 / 1,170 / 19
        .txt 2 / 586 / 18             .env 1 / 344 / 7

NNG's exact gap bytes, against the KB table above: `.jsp` 608,420, `.properties` 82,689, `.css`
55,788, `.ent` 30,267, `.xml` 25,217, `.vm` 18,219, `.tld` 2,550, `.xmi` 804 — eight rows and no
more.

**The `(none)` row exists on one corpus and not the other, and the asymmetry is instructive.** On
ctcm-api it is 22 files / 36,769 bytes / 967 lines — 19 `Dockerfile`s (one per service), 2
`.dockerignore` and 1 `.editorconfig` (9,912 bytes, the largest single file in the row) — making it
the sixth-largest gap row by bytes. On **NNG there is no `(none)` row at all**: the corpus holds 71
extension-less files inside the walk and every one is already claimed, 69 first-party excluded and 2
credential. So `ExtensionRow.extension == ""` is a real display case with a real corpus behind it,
and a plan reader who only ever looks at NNG will not know it exists.

**NNG's four credential files, by path** — two of them extension-less, which is why the tier is
reached through `CREDENTIAL_NAMES` matching the *name* rather than through `CREDENTIAL_EXTENSIONS`,
and why a `credential_files` display keyed on extension shows two blanks:

        ple-web-api/src/main/resources/server-key.p12     9,903 bytes   47 lines   ".p12"
        ple-web-api/src/main/resources/ssTrustStore      11,206 bytes   49 lines   ""
        ple-web/src/main/resources/server-key.p12         9,903 bytes   47 lines   ".p12"
        ple-web/src/main/resources/ssTrustStore          11,206 bytes   49 lines   ""

**ctcm-api's referenced-content tier, composed** — 57 `.docx` (10,208,966 bytes), 1 `.pdf` (65,448)
and 1 `.doc` (50,176). The byte spread is what makes this tier 10,083 KB against a 373 KB gap: median
35,226, mean 174,993, max 2,731,180, and the four files over 1 MB carry 79.7% of it. The directory
split matters for M3's "57 of 58" claim: **58 files under
`src/CTCM.API/CTCM.API.DocumentService/Templates/`** (the 57 `.docx` plus `RehabConsultationReport
Template.doc`) and **one elsewhere** —
`src/CTCM.API/CTCM.API.WorkflowService/EmailTemplates/Attachments/AssessmentInstructions.pdf`, which
is in neither the `Templates/` directory nor the `TemplateNames.cs` constants class, and so is not
the file M3's zero-reference check is expected to flag.

*Both corpora*, on the labels rather than the totals — these are the assertions the probe cannot
make for you, because it implements neither the `detect_language` nor the `max_file_bytes` gate and
has no `rejected_by` at all:

- Every gap file carries `rejected_by="include_globs"`, so each `ExtensionRow.rejected_by` is exactly
  `{"include_globs": <that row's file count>}`. A row with any other key is new information about
  the corpus, not a test failure — but on these two corpora it does not occur.
- Every file in the `first-party excluded` tier carries a non-`None` `matched_glob`, every value is
  one of the patterns actually passed in, and `first_party_excluded_by_glob` sums to
  482 files / 2,669 KB on NNG and to nothing at all on ctcm-api.
- `len(gap_files)` equals the `gap` tier's file count — 276 on NNG, 186 on ctcm-api — and equals the
  sum of `ExtensionRow.files` across `gap_by_extension`.

### M2

Both of the above reproduce through the CLI rather than the probe, in a `rich` table and in `--json`,
with the mode named in the output. In addition:

- The raw (pre-suppression) headline is reported alongside the post-suppression one. NNG: about
  **63.0% of bytes and 55.3% of lines**, against 19.60%/17.55% after suppression. ctcm-api: about
  **47.9% of bytes and 14.1% of lines**, against 3.15%/3.14%. These are pinned to one decimal because
  they are derived here from the rounded column; the implementation should compute them from exact
  bytes. The ctcm-api pair diverging by more than thirty points is the intended diagnostic, not a
  defect: it says the remaining raw mass is a handful of huge binaries.
- `--limit` truncates the displayed rows while the totals stay exact over the full set, and `--json`
  is complete regardless of `--limit`. Check it concretely: `--limit 3 --json` and `--limit 20 --json`
  return identical row counts in `gap_files`, `gap_by_extension`, `dropped`, `referenced_content`
  and `symbolless_files`, and identical totals.
- `--json` carries `schema_version: 1` and lists every dropped third-party file with the rule that
  dropped it; it also carries `gap_files` with a `rejected_by` on every row,
  `first_party_excluded_by_glob`, `domains_source` and `provenance_degraded`.
- The three modes behave per the table in `Interfaces and Dependencies`, verified as three runs
  against ctcm-api with `--index-dir` pointed at a nonexistent directory:
  `--mode predicted` exits 0 and prints the same tier table (no reconciliation line, no check two);
  `--mode auto` exits 0, prints the same table, reports `mode: "predicted"` in the JSON and says so
  on stderr; `--mode observed` exits 1 with a message naming the path it looked at.
- **`--mode predicted` must also be checked where an index *does* exist**, because that is the case
  the obvious implementation gets wrong — gating the open on `sqlite_path.exists()` alone silently
  promotes a `predicted` run to observed. Run it against NNG with no `--index-dir` at all (its index
  resolves and is present): the JSON must still say `mode: "predicted"`, `reconciliation` must be
  absent and `symbolless_files` empty. The same applies to ctcm-api, whose index is also present at
  its default resolved path — neither corpus reaches predicted mode by accident.
- A bad `--repo-root` exits 1 with a one-line message naming the path, **not** a Python traceback.
  `resolve_paths` raises a bare `FileNotFoundError`, so this fails unless the call is wrapped; check
  it with a path that does not exist and confirm no `Traceback` appears in the output.
- Exit status is 0 whenever the walk completes, including when the gap is large. Verify explicitly
  with `echo $?` — a nonzero exit on a completed walk is a defect, not a feature. The `--mode
  observed` usage error above is the only sanctioned nonzero exit.
- Running NNG on the `--domains` default (its live `domains.json`) sets `provenance_degraded: true`,
  warns on stderr, and does **not** reproduce the pinned numbers; running it against the Step 3
  scratch file sets `provenance_degraded: false` and does. `--domains none` also exits 0.

### M3

- Check two on NNG returns **8 raw and 5 after exclusion**, listing
  `ple-persistence/sql/FarmTapEntry.sql`,
  `ple-persistence/sql/data-cleanup-queries/Find Tables with Bad Dates.sql`,
  `db/PLEConfiguration-Update-Rollback.sql`, `db/PLEConfiguration-Update.sql` and
  `ple-persistence/JavaSource/config/hbm/external/DunsSetup.hbm.xml`.
- Check two on ctcm-api returns **0**. The negative result is required: it is what proves the check
  discriminates.
- Referenced content on ctcm-api: **59 files, 58 with at least one indexed reference, exactly one
  flagged zero-reference** —
  `src/CTCM.API/CTCM.API.DocumentService/Templates/RequestforMediation.docx`. Adding the
  `symbol_refs` half of the lookup to the chunk-text half must not change that split; if the
  zero-reference count moves, the reference resolution is matching something it should not.
- The reconciliation line reports `repo_files=1229, indexed tier=871, delta=358` on NNG and
  `repo_files=4715, indexed tier=4715, delta=0` on ctcm-api, and states that the delta is the
  first-party exclusion. Observed mode must not list those 358 files as walk-versus-index
  discrepancies.

### M4

Re-run every M1–M3 acceptance check with the acceptance manifest removed, so the defaults in
`config.py` supply `**/legacylift-docs/**`. **Every number above must be identical.** Additionally,
`indexed` must remain 871 on NNG and 4,715 on ctcm-api — that equality is the evidence the new glob
excludes nothing the index actually holds. Note that the asset and referenced-content extension sets
are *not* affected by M4, because they are tier-membership rules inside the walk and never manifest
exclusions; only `**/legacylift-docs/**` moves the walk total.

Finally, the whole suite:

    cd <checkout>/tools/legacylift_search
    PYTHONPATH="$PWD/src" <venv python> -m pytest

expecting **1,250** — the post-widening floor: the post-merge 1,207 plus the coverage widening's 43. That 1,207 is the requirements branch's 1,159 plus M0's 18, M1's 28 and
the 2 `DomainsFile` tests. (Before the 2026-09-03 merge this read 456, from the 2026-09-01 baseline
of 408 on this branch alone.) Add to that the tests M2–M3 contribute, with no failures.

## Idempotence and Recovery

Every step here is safe to repeat.

`gaps` is a **read-only** command. It opens files for reading, opens `index.sqlite` through
`SQLiteStore(path, read_only=True)` — the additive keyword M3 adds, which uses SQLite's
`file:...?mode=ro` URI form rather than the plain read/write `sqlite3.connect` at `store.py:175` —
never calls `migrate()`, writes no report or artifact of its own, and changes no row of any
database. Running it repeatedly, concurrently, or against a partially built
index cannot damage anything; the worst outcome is a number computed from a stale index, which is
why the mode is named in the output.

**One honest exception, and do not delete this sentence when you implement the keyword.** A
`mode=ro` handle on a WAL database creates the `-wal` and `-shm` sidecar files if they are absent,
which on a cleanly closed index they are. So `gaps` touches the filesystem beside the index even
though it writes no data — measured, with the transcript, in `Surprises & Discoveries`. The
consequence that matters operationally is that an index sitting on a read-only filesystem cannot be
opened at all. `&immutable=1` would avoid both and was rejected, because it forfeits the
concurrent-writer safety promised in the paragraph above — see the `Decision Log`. So the claim is
scoped deliberately: no data is modified, and two sidecar files may appear beside the index.

`scripts/refresh_linguist.py` overwrites `profiles/linguist.json` in place. It is safe to re-run; if
a refresh produces a bad file, `tests/test_linguist_profile.py` fails — that is the point of the
test — and recovery is `git checkout` of the JSON. Never edit that file by hand: it records an
upstream commit SHA, and a hand edit makes the SHA a lie.

M4's manifest-default change is additive and affects only which files the *walk* considers. It cannot
remove anything from an existing index and requires no reindex; verified on both corpora by the
`indexed` tier being unchanged. If it ever did change an index, the recovery is to remove the glob
and re-run `index`.

The credential tier never reads file contents, so no step in this plan can copy a secret into a log,
a report or a JSON payload.

The Step 3 acceptance fixtures live in `active/artifacts/`, never inside a corpus, so no acceptance
run leaves anything behind in a client checkout. Both are inputs only; nothing writes to them.

## Artifacts and Notes

**The probe.** `docs/exec-plans/active/artifacts/gap-detection-probe.py` implements the settled walk
and prints expected-versus-measured for each corpus. It is not production code and nothing imports
it. It also carries the Q27 re-classification of NNG's 45 `domain_exclusions` patterns into
`NNG_VENDORED` and `NNG_FIRSTPARTY` — without those lists the acceptance numbers cannot be
reproduced, because the live `knowledge.sqlite` still holds the un-split original.

**What the probe is not the oracle for.** It applies `include_globs` and stops there
(`gap-detection-probe.py:252-253`): it never calls `detect_language`, never checks `max_file_bytes`,
and has no `rejected_by`, no `matched_glob` and no `first_party_excluded_by_glob`. It is therefore
the oracle for the *numbers* only. M1's `language` and `size_cap` labels, and every label assertion
in the M1 acceptance criteria, are verified by unit tests alone. That is sound — neither gate fires
on either corpus, which is itself a measured claim — but "run the probe, do not reason about it"
must not be read as covering them.

**What M0 shipped, and where** (commit `7925149a`, 2026-09-02). Four new files plus one:

        tools/legacylift_search/scripts/refresh_linguist.py               generator, by hand only
        tools/legacylift_search/src/legacylift_search/profiles/linguist.json   254 KB, LF-pinned
        tools/legacylift_search/src/legacylift_search/linguist.py         loader, 4 functions
        tools/legacylift_search/tests/test_linguist_profile.py            18 tests
        .gitattributes                                                   new at the repo root

M1 needs only `linguist.py`: `load_linguist_profile()` (defaults to the packaged path),
`classify_extension(profile, ".jsp")` and `classify_filename(profile, "Jenkinsfile")` for the two
triage columns, `tree_sitter_grammar_for(".dtd")` for the third, and
`profile.vendor_filename_patterns` for provenance rule 2 — that list is already the adopted 113, so
M1 does no splitting of its own. `pyproject.toml` was not touched and must not be:
`packages.find where=["src"]` leaves `scripts/` unpackaged, `package-data` already ships
`profiles/*.json`, and `pyyaml` stays out of the runtime dependencies.

**What M1 shipped, and where** (2026-09-02):

        tools/legacylift_search/src/legacylift_search/gaps.py            the walk, ~410 lines
        tools/legacylift_search/tests/test_gaps_walk.py                  28 tests
        tools/legacylift_search/src/legacylift_search/domain_tagger.py   +2 additive fields
        tools/legacylift_search/tests/test_domain_tagger.py              +2 tests

M2 needs from it: `walk_repository`, `WalkResult`, `WalkedFile` (with `rejected_by` and
`matched_glob` already populated), and `DroppedFile` — which now carries `size_bytes` and
`line_count`, so the `third-party DROPPED` row and both raw headlines are computable without touching
the filesystem a second time. `Tier` and `TIER_ORDER` are exported; `TIER_ORDER` is the report's key
order for `totals`, **not** the tiering precedence, which is credential-first and lives in the walk.

**The acceptance inputs and runners are committed**, in `active/artifacts/` beside the probe:
`gap-acceptance-manifest.json`, `gap-acceptance-domains-nng.json`, `gap-acceptance-walk.py` and
`gap-acceptance-labels.py`. Step 3 says how to run them. They were scratch files during M1 and were
committed at the end of it for one reason: every acceptance number in this plan is reproducible only
with those two fixtures, and reconstructing them by hand from `config.py` and the probe's constants
is both tedious and easy to get subtly wrong. The manifest stops being necessary when M4 makes
`**/legacylift-docs/**` a default; the domains file stops being necessary when `/modernize-assess`
authors the two lists into NNG's real `domains.json`. Delete each one at that point, not before.

**M0 was de-risked before implementation.** Both upstream YAML files were fetched on 2026-09-01 and
every resolution this plan pins was verified against them. Transcript:

        languages: 833
        extensions keys: 1486
        filenames keys: 419
          .jsp          [('Java Server Pages', 'programming', 'Java')]
          .tld          (absent)
          .xsd          [('XML', 'data', None)]
          .dtd          (absent)
          .css          [('CSS', 'markup', None)]
          .properties   [('INI', 'data', None), ('Java Properties', 'data', None)]
          .vm           (absent)
          .png          (absent)
          Jenkinsfile   [('Groovy', 'programming', None)]
          .gitignore    [('Ignore List', 'data', None)]
        vendor.yml regexes: 168 filename: 113 directory: 55

and, against the installed `tree-sitter-language-pack` 1.8.1 (306 grammars):

        'dtd'  -> dtd          '.dtd' -> None
        has_language('css') True   has_language('jsp') False   has_language('dtd') True

**Third-party drop attribution**, which is the evidence behind the `--json` requirement that every
dropped file names the rule that dropped it:

        ctcm:
          vendor.yml         (^|/)\.gitattributes$    .gitattributes
          vendor.yml         (^|/)\.gitignore$        .gitignore
          declared-identity  http://iaiabc.org/Schema src/CTCM.API/CTCM.API.EdiService/Xml/xsd/Release30POC.xsd
          declared-identity  http://iaiabc.org/Schema src/CTCM.API/CTCM.API.EdiService/Xml/xsd/Release31Claims.xsd
          declared-identity  http://iaiabc.org/Schema src/CTCM.API/CTCM.API.EdiService.Tests/Xml/xsd/Release30POC.xsd
          COUNTS {'vendor.yml': 2, 'declared-identity': 3}

        nng:
          declared-identity  http://www.springframework.org/tags   ple-web/.../WEB-INF/tld/spring.tld
          declared-identity  http://tiles.apache.org/tags-tiles    ple-web/.../WEB-INF/tld/tiles-jsp.tld
          COUNTS {'vendor.yml': 12, 'declared-identity': 29, 'vendored_globs': 31}

**Deferred and spun out.** Three measurements taken during the design interview became their own
drafts rather than parts of this one: `pending/durable-loc-counts.md`,
`pending/embed-everything-evaluation.md`, and `pending/deferred-small-items.md` — whose items 1 and 2
came from this work (`/modernize-status` surfacing the gap percentage in its §4 verdict; the
unprefixed Spring Webflow state kinds in `xml_extractor.py:251-253`). One decision was implemented
rather than deferred: `/modernize-status` §2 gained a staleness rule comparing the discovery
artifacts against the Layer-0 index and `knowledge.sqlite`.

One follow-on is worth naming here because this plan creates the need for it and does not satisfy it:
nothing currently authors `own_identities` into `domains.json`. `/modernize-assess` is the natural
place — it already identifies the client organization — and until it does, the token comes from
`--own-identity` on the command line. The measured cost of omitting it is in the `Decision Log`.

## Interfaces and Dependencies

No new runtime dependency. `pyyaml` is imported by `scripts/refresh_linguist.py` only, which is a
development script, is not packaged, and must not be added to `pyproject.toml`. `pathspec`, `pydantic`,
`rich`, `typer` and `tree-sitter-language-pack` are all already declared.

In `tools/legacylift_search/src/legacylift_search/linguist.py` (new, M0), define:

    class LinguistLanguage(BaseModel):
        name: str
        type: str | None          # "programming" | "markup" | "data" | "prose"
        group: str | None

    class LinguistProfile(BaseModel):
        schema_version: int
        attribution: str
        upstream_commit: str
        fetched_at: str
        upstream_language_count: int   # languages.yml's own count; see below
        extensions: dict[str, list[LinguistLanguage]]
        filenames: dict[str, list[LinguistLanguage]]
        vendor_filename_patterns: list[str]
        vendor_directory_patterns: list[str]

    def load_linguist_profile(path: Path | None = None) -> LinguistProfile: ...
    def classify_extension(profile: LinguistProfile, ext: str) -> list[LinguistLanguage]: ...
    def classify_filename(profile: LinguistProfile, name: str) -> list[LinguistLanguage]: ...
    def tree_sitter_grammar_for(ext: str) -> str | None: ...

`load_linguist_profile` defaults to `Path(__file__).resolve().parent / "profiles" / "linguist.json"`,
matching how `cli.py:1727-1729` loads `extractors.json`. `tree_sitter_grammar_for` takes the
extension **with** a leading dot and strips it before calling
`tree_sitter_language_pack.detect_language_from_extension`, so the leading-dot trap is handled in one
place and cannot be repeated at a call site.

`upstream_language_count` exists because the pruned maps cannot express it, which M0 discovered on
implementation: 6 of the pinned snapshot's 833 languages are reachable by neither an extension nor a
filename, so 827 distinct names survive pruning and "833" is unassertable from the two maps alone.
It is a scalar copied from `len(languages.yml)` at fetch time, and asserting it *beside* the 827
separates a changed upstream from a broken inversion — see `Surprises & Discoveries`.

`classify_extension` also takes the extension **with** a leading dot and casefolds it before lookup,
matching `detect_language`; `classify_filename` matches exactly and must not casefold. Both traps
therefore live in one place each. `LinguistLanguage.type` is typed optional for schema tolerance
only: no language in the pinned snapshot omits it (0 of 833, measured 2026-09-02), so the `None`
branch is unreachable from the vendored data and must not be given a test that pretends otherwise.

In `tools/legacylift_search/src/legacylift_search/gaps.py` (new, M1 and M3), define:

    Tier = Literal["indexed", "credential", "referenced_content", "asset",
                   "first_party_excluded", "gap"]

    class WalkedFile(BaseModel):
        relative_path: str
        extension: str                  # ".jsp", or "" when the file has none
        size_bytes: int
        line_count: int
        tier: Tier
        rejected_by: Literal["include_globs", "language", "size_cap"] | None
        matched_glob: str | None        # first-party exclusion pattern that claimed it, else None

    class DroppedFile(BaseModel):
        relative_path: str
        rule: Literal["declared_identity", "vendor_filename", "vendored_globs"]
        detail: str                     # the declared identity, or the pattern that matched
        size_bytes: int                 # both counted during the walk: M2's raw headline is
        line_count: int                 # defined over the tiers PLUS the drops

    class TierTotals(BaseModel):
        files: int
        size_bytes: int
        line_count: int

    class WalkResult(BaseModel):
        files: list[WalkedFile]
        dropped: list[DroppedFile]
        rescued_by_identity: list[str]  # first-party files a vendored glob claimed
        totals: dict[Tier, TierTotals]

    def walk_repository(
        repo_root: Path,
        manifest: Manifest,
        *,
        profile: LinguistProfile,
        first_party_exclude_globs: Sequence[str] = (),
        vendored_globs: Sequence[str] = (),
        own_identities: Sequence[str] = (),
    ) -> WalkResult: ...

**As built (2026-09-02), and this is what M2 imports.** The four models and the `walk_repository`
signature above shipped field-for-field as specified — nothing renamed, no type changed, no field
carrying a default — with the two additive `DroppedFile` counters noted in their comment. Beyond
them, `gaps.__all__` exports six names the block above never mentions:

    TIER_ORDER                    = ("indexed","credential","referenced_content","asset",
                                     "first_party_excluded","gap")
    CREDENTIAL_EXTENSIONS         = {".p12",".jks",".keystore",".pfx",".pem"}
    CREDENTIAL_NAMES              = {"sstruststore","cacerts"}      # vs name AND stem, casefolded
    REFERENCED_CONTENT_EXTENSIONS = {".docx",".doc",".xlsx",".xls",".pptx",".ppt",".pdf",".zip"}
    ASSET_EXTENSIONS              = {".png",".jpg",".jpeg",".gif",".psd",".ico",".bmp",".svg",
                                     ".woff",".woff2",".ttf",".eot"}
    IDENTITY_EXTENSIONS           = {".tld",".xsd",".dtd"}

all `frozenset`s of lowercase literals. Everything else in the module is private, including
`_IDENTITY_HEAD_BYTES = 8000` and `_deciding_glob` — the latter will tempt an M2 implementer building
`first_party_excluded_by_glob`, and it is not needed, because `WalkedFile.matched_glob` already
carries its answer per file.

**`TIER_ORDER` is not the order the tables in this plan print.** It is `WalkResult.totals`' key order,
`indexed → credential → referenced_content → asset → first_party_excluded → gap`. Every acceptance
table here, and the probe, print `indexed → gap → first-party excl → referenced content → asset →
credential`. Both are written down as authoritative and they disagree; the acceptance criteria pin the
second, so the rich table must use it and `TIER_ORDER` must not be mistaken for a display order.

Three more properties of the shipped module, none of them in the block above and each capable of
surprising a caller. `walk_repository` calls `repo_root.resolve()` on entry, so every `relative_path`
is relative to the *resolved* root rather than to the path passed in. The models are permissive
`BaseModel`s — no `extra="forbid"`, so an unknown keyword is silently ignored — and `TierTotals` is
mutable and mutated in place during the walk, so a caller holding `walk.totals["indexed"]` holds a
live object. And `WalkResult.model_dump_json()` round-trips cleanly with `totals` keyed by the tier
strings, so `--json` needs no custom encoder.

**Ordering is filesystem order, not a contract.** `files` comes out in `Path.rglob("*")` traversal
order (per-directory, root files before subdirectories) and `dropped` in walk order; neither is
sorted, grouped by tier, or stable across platforms. M2 must sort explicitly before display or the
table will differ between machines.

**Every `relative_path` in this feature is a repo-relative POSIX string** — forward slashes on every
platform, built once per file as `path.relative_to(repo_root).as_posix()` and then used unchanged for
glob matching, `vendor.yml` regex matching, tier attribution, the `repo_files` join and display. The
rule covers `WalkedFile`, `DroppedFile`, `ReferencedContentFile`, `SymbollessFile`,
`WalkResult.rescued_by_identity`, `Reconciliation.unexplained` and `GapReport.credential_files`.

This is not a style preference, it is the convention the code already has, and it is load-bearing in
three separate places. `discovery.py:63` builds exactly that string and matches `exclude_globs` and
`include_globs` against it at lines 69 and 73, so a walk holding native separators would disagree
with the allow-list it exists to model — on Windows, `**/*.java` does not match `a\foo.java`.
`vendor.yml`'s patterns are anchored on `/` (`(^|/)\.gitattributes$`), so a backslash path silently
drops out of provenance rule 2. And M3's reconciliation joins these strings against
`repo_files.relative_path`, which is POSIX in every row: measured 2026-09-02 across both live
indexes, **0 of 5,944 rows contain a backslash** (NNG 1,229, ctcm-api 4,715). A native-separator walk
would therefore reconcile to a delta equal to the whole tree on Windows and to zero on Linux — a bug
that passes CI on one platform and is invisible on the other, which is why it is pinned here rather
than left to whichever call site converts first.

Construct it once, in the walk, and never re-derive it downstream. `Path` objects stay internal to
`walk_repository`; nothing in `WalkResult` or `GapReport` carries one.

and, for **M2** — an earlier revision labelled this whole block "for M3", which is wrong and would
send an M2 implementer looking for the work in the next milestone. Sixteen of `GapReport`'s nineteen
fields are computable from `WalkResult` plus the CLI; **only three need the store**, and they are
`symbolless_files`, `reconciliation`, and `ReferencedContentFile.reference_count` / `zero_reference`.
The split is tabulated under `M2 — the gaps command`:

    class ExtensionRow(BaseModel):
        extension: str                  # ".jsp", or "" when the files have none
        files: int
        size_bytes: int
        line_count: int
        linguist_languages: list[LinguistLanguage]   # empty when unknown to linguist
        tree_sitter_grammar: str | None              # None when no grammar claims the extension
        rejected_by: dict[str, int] = {}             # {"include_globs": 178} -- gate counts for this row

    class ReferencedContentFile(BaseModel):
        relative_path: str
        reference_count: int
        zero_reference: bool

    class SymbollessFile(BaseModel):
        relative_path: str
        size_bytes: int
        language: str

    class Reconciliation(BaseModel):
        repo_files_rows: int
        indexed_tier_files: int
        delta: int
        unexplained: list[str]

    class GapReport(BaseModel):
        schema_version: int = 1
        mode: Literal["observed", "predicted"]
        repo_root: str
        totals: dict[Tier, TierTotals]
        walk_total: TierTotals
        headline_bytes_pct: float
        headline_lines_pct: float
        raw_headline_bytes_pct: float
        raw_headline_lines_pct: float
        gap_by_extension: list[ExtensionRow]
        gap_files: list[WalkedFile]                        # complete; the display path truncates
        first_party_excluded_by_glob: dict[str, TierTotals]
        dropped: list[DroppedFile]
        rescued_by_identity: list[str]  # M1 computes it and the M1 criteria name two paths from
                                        # it; without this field the payload cannot carry it
        credential_files: list[str]
        referenced_content: list[ReferencedContentFile]
        symbolless_files: list[SymbollessFile]
        reconciliation: Reconciliation | None
        domains_source: str | None      # the resolved domains.json, or None
        provenance_degraded: bool       # that file carried no vendored_globs and no own_identities

    def build_gap_report(
        walk: WalkResult,
        *,
        profile: LinguistProfile,
        store: SQLiteStore | None = None,
        min_bytes: int = 2048,
    ) -> GapReport: ...

`profile` is **required**, and it belongs on this function rather than on `WalkResult` because
`ExtensionRow.linguist_languages` and `ExtensionRow.tree_sitter_grammar` cannot be populated without
it. An earlier revision of this block omitted it, which made both of the report's triage columns
unreachable from the specified signature; `WalkResult` stays a pure data record so the M1 fixtures
never have to carry a profile alongside every serialized walk.

There is deliberately **no `limit` parameter**. Truncation is the caller's job in the display path
only — `GapReport` always carries the complete lists, following `SQLiteStore.coverage`'s documented
discipline at `store.py:1085-1087` — and a `limit` on the producer contradicts that in the one place
an implementer would look for permission to truncate early.

`gap_files` carries every gap file with its `rejected_by` label and, for the first-party tier, its
`matched_glob`; `ExtensionRow.rejected_by` is the same information aggregated per extension, and
`first_party_excluded_by_glob` is the ranked "excluded on purpose, and under which glob" table the
`Purpose` section promises. Without these three, the labels the walk computes in M1 have nowhere to
go and `--json` cannot answer "add a glob" versus "write a parser" — the question the labels exist
for.

`store=None` selects predicted mode; `reconciliation` and `symbolless_files` are then absent. When a
store *is* passed it must be opened read-only — see the `SQLiteStore` note below — because `gaps`
modifies no data.

**Do not read "or zero" into the `reference_count` half of that rule, which an earlier revision said.**
In predicted mode the referenced-content *rows* are fully known — they come from the walk's tier, 59
of them on ctcm-api — and only the reference count is unknowable. Setting it to `0` sets
`zero_reference` on all 59 and reports fifty-nine findings where M3 reports one, which is worse than
saying nothing. Predicted mode must leave the count **absent** and `zero_reference` unset, and the
display must say the column is unavailable rather than print zeros. Make `reference_count:
int | None` and `zero_reference: bool | None` if that is what it takes.

`min_bytes` and `store` are M3's parameters and do nothing in the M2 slice; an M2 implementer will
look for the code that consumes them and correctly find none.

In `tools/legacylift_search/src/legacylift_search/cli.py` (M2), add:

    @app.command("gaps")
    def gaps(
        repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
        config: Optional[Path] = typer.Option(None, "--config"),
        index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
        analysis_dir: Optional[Path] = typer.Option(None, "--analysis-dir"),
        domains: Optional[str] = typer.Option(None, "--domains"),   # a path, or the literal "none"
        own_identity: list[str] = typer.Option([], "--own-identity"),
        mode: str = typer.Option("auto", "--mode"),          # auto | observed | predicted
        min_bytes: int = typer.Option(2048, "--min-bytes"),
        limit: int = typer.Option(20, "--limit"),
        json_output: bool = typer.Option(False, "--json/--no-json"),
    ) -> None: ...

Path resolution uses the existing `cli_helpers.resolve_paths(...)`, the same convention `stats` and
`coverage` follow, including the `--analysis-dir` override. It must **not** use
`cli_helpers.open_store_or_exit(...)`: that helper raises `typer.Exit(code=1)` when the SQLite file
is missing (`cli_helpers.py:135-140`), which is right for `stats` and wrong here, because `gaps` is
specified to work before `index` has ever run. Do the existence check inline instead — and note two
things the obvious three-line version gets wrong:

    try:
        manifest, root, index = resolve_paths(repo_root, config, index_dir, analysis_dir)
    except Exception as exc:                       # resolve_paths raises a BARE
        console.print(f"[red]{exc}[/red]")         # FileNotFoundError for a missing
        raise typer.Exit(code=1)                   # --repo-root (cli_helpers.py:80-81)

    sqlite_path = index / manifest.index.sqlite_file
    if mode == "predicted":
        store = None                               # never opened, even if it exists
    elif sqlite_path.exists():
        store = SQLiteStore(sqlite_path, read_only=True)
    elif mode == "observed":
        console.print(f"[red]--mode observed: no index at {sqlite_path}[/red]")
        raise typer.Exit(code=1)
    else:                                          # auto, index absent
        store = None

First, `resolve_paths` raises an unwrapped `FileNotFoundError` when `--repo-root` does not exist. Let
it escape and the user gets a Python traceback, not the usage error this plan promises; `typer` does
not translate it. `open_store_or_exit` wraps it for exactly this reason at `cli_helpers.py:122-128`
— copy that behaviour, since dropping the helper also drops its error handling.

Second, the open must be gated on `--mode`, not on file existence alone. `--mode predicted` is
specified to work without a database at all, and a `predicted` run that silently opens an index it
found is both a contract violation and — see the `SQLiteStore` note below — a write to disk.

`--mode` then has exactly three behaviours, and this table is the contract:

| `--mode`           | index missing                                          | exit |
|--------------------|--------------------------------------------------------|------|
| `predicted`        | never opened at all                                    | 0    |
| `auto` *(default)* | degrades to predicted; says so on stderr and in `mode` | 0    |
| `observed`         | usage error, message names the path it looked at       | 1    |

`--domains` defaults to `<analysis_dir>/domains.json` when `config.resolve_analysis_dir` finds an
analysis directory and that file exists; `--domains none` suppresses the default explicitly.

**That default carries a guard, and the guard is not optional.** Measured 2026-09-02, NNG's live
`domains.json` holds `exclude_globs` 45, `vendored_globs` 0 and no `own_identities` — it is still the
pre-split mixture Q27 re-classified. Taking the default on the very corpus this plan pins therefore
reproduces none of the numbers below, and gives no sign of it. So when the resolved file carries
neither `vendored_globs` nor `own_identities`, warn on stderr naming the file, its `exclude_globs`
count, the fact that third-party provenance has degraded to `vendor.yml` filename patterns alone,
and that `/modernize-assess` needs re-running (its two-list prompt shipped 2026-09-01). Record the
same fact in the payload as `provenance_degraded: true` beside `domains_source`, so a consumer can
tell a clean run from a degraded one without reading stderr.

In `tools/legacylift_search/src/legacylift_search/domain_tagger.py` (M1), `DomainsFile` gains two
optional fields alongside the existing `exclude_globs`:

    vendored_globs: list[str] = []
    own_identities: list[str] = []

In `tools/legacylift_search/src/legacylift_search/store.py` (M3), `SQLiteStore.__init__` gains one
optional keyword, `read_only: bool = False`, and `_connect` honours it by opening a `file:` URI in
place of the plain path form at `store.py:175`. The change is additive — every existing caller keeps
the read/write connection it has today — and `gaps` never calls `migrate()`. Interpolating the
`Path` directly is fine: measured 2026-09-02, `f"file:{path}?mode=ro"` with Windows backslashes
opens the real NNG index and reads 1,229 `repo_files` rows, so no `as_posix()` step is needed.

The URI form is settled — use `mode=ro` and nothing else:

    sqlite3.connect(f"file:{self.sqlite_path}?mode=ro", uri=True)

Do **not** add `&immutable=1`, even though it is the only form that creates no files. The reasoning
is in the `Decision Log`; the short version is that concurrent-writer safety is worth more than a
literal write-free claim, so the claim was narrowed instead. Two consequences to implement rather
than discover: a `gaps` run may create `-wal`/`-shm` beside the index, and an index on a read-only
filesystem cannot be opened at all — if that ever needs to work, `immutable=1` becomes an opt-in
flag, never the default.

In `tools/legacylift_search/src/legacylift_search/config.py` (M4), `ProjectConfig.exclude_globs`
gains one entry, `"**/legacylift-docs/**"`, beside the existing `"**/legacylift-docs/index/**"`.

Skill files touched: `.claude/skills/code-modernization/commands/modernize-assess.md` only, in M4.
`/modernize-status` needs no edit and gains no behaviour.

---

**Revision note.** This file was rewritten on 2026-09-01 from its pre-interview draft form into a
conforming ExecPlan, sourced from `pending/layer0-extraction-gap-detection-decision.md`. The draft's
*"The problem, stated as a measurement"* section was replaced with the record's §2 and §2b
measurements, re-measured on the day with the committed probe; its `.gitignore` requirement was
deleted because nothing in the toolchain reads one; the cause was re-attributed from `detect_language`
to `include_globs`, which is the gate that actually produces the gap and is two steps earlier; its
*"Open questions"* section was replaced with the settled design; and a Plan of Work, Concrete Steps
and acceptance criteria pinned against **both** corpora were added for M0–M4. The reason for the
rewrite is that the draft's specification for check one returns the empty set by construction, its
numbers were roughly 2× too high because it counted build duplicates that manifest `exclude_globs`
already drops, and it left four questions open that have since been decided. Three further decisions
that the record did not make — how an own-identity token is supplied, where the two authored glob
lists are read from, and how the raw headline is defined — were resolved while writing this plan and
are recorded with their rationale in the `Decision Log`.

**Revision note, 2026-09-02 (second verification pass).** A second review pass went looking
specifically for defects the 2026-09-02 first pass missed and for consequences its own fixes
introduced, and found six. Five are fixed here.

The one that mattered most was created by the first pass: it introduced two-step SHA pinning for the
linguist fetch and then asserted that the M0 volume numbers are "properties of the committed file
rather than of a moving upstream branch" — while Step 1 still said `--ref main` and no 40-hex SHA
appeared anywhere in the plan, the decision record or the probe. The assertion is only true after
someone has committed a JSON, so the *first* generation could not reproduce the pinned volumes by
construction, and M0's test would have failed on its first execution with no way to tell a broken
refresh from an upstream release. Resolved by resolving `main` and re-measuring: commit
`d5214e1612c858ba14bf98edeca57e1683276f1d` (2026-09-01T09:40:55Z) reproduces 833 / 1,486 / 419 /
113 / 55 and every pinned resolution, so it is now written into the M0 narrative, Step 1, the
acceptance criteria and `Progress`.

The other four fixes: the CLI snippet the first pass added opened the store on `sqlite_path.exists()`
alone, contradicting its own `--mode` table (`predicted` → "never opened at all"), and dropped
`open_store_or_exit`'s error handling along with the helper, so an unreadable `--repo-root` would
have produced a traceback instead of the required usage message — both corrected in the snippet and
pinned by two new M2 acceptance checks. `matched_glob` and `first_party_excluded_by_glob`, also
first-pass additions, were specified with no rule for which glob owns a file that several match; the
tier bullet now states that gitignore dialect makes the *last* match decide, that a `!` pattern
un-excludes, and that `pathspec.PathSpec.check_file` is the API that reports it. M2's prose claimed
observed mode is the only mode that can see a `max_file_bytes` drop, which M1's own `size_cap` label
contradicts; only the read-error half is observed-only. And the claim that ctcm-api "exercises
predicted mode" was retracted in both this plan and the probe's comment: predicted versus observed
turns on `index.sqlite`, not the `knowledge.sqlite` ctcm-api lacks, and its index is present at the
default resolved path with 4,715 rows. Separately, the `.gitignore` imprecision's cost was restated
from "two small files on ctcm-api" to include NNG's nine, which are 9 of that corpus's 12
`vendor.yml` drops and make two `NNG_FIRSTPARTY` patterns dead.

The sixth finding was a design choice rather than an error, and was put to the maintainer rather than
fixed unilaterally: `?mode=ro` on a WAL database creates the `-wal` and `-shm` sidecars, so the first
pass's read-only keyword did not make the "writes nothing" claim structural the way it said it did.
`immutable=1` would, but forfeits the concurrent-writer safety the same paragraph promises. Decided
2026-09-02 in favour of keeping `mode=ro` and narrowing the claim to "modifies no data", on the
grounds that `gaps` is a diagnostic people run while deciding whether to reindex and so is the
command most likely to be aimed at a database being written. The measurement is in
`Surprises & Discoveries`, the reasoning and rejected alternative in the `Decision Log`, and
`Idempotence and Recovery` now states the sidecar behaviour instead of promising it away.
